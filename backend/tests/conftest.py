import os

os.environ["APP_ENV"] = "test"
os.environ.setdefault("SECRET_KEY", "test-signing-key-for-automated-tests-only-1234567890")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://schoolerp:test-only@127.0.0.1:5432/schoolerp_test"
)
os.environ.setdefault("SUPER_ADMIN_USERNAME", "superadmin")
os.environ.setdefault("SUPER_ADMIN_EMAIL", "superadmin@schoolerp.test")
os.environ.setdefault("SUPER_ADMIN_PASSWORD", "QaTest@2026!Strong")

import asyncio
from collections.abc import AsyncGenerator

import pytest
import app.models  # noqa: F401 - register all ORM tables before create_all
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine as app_engine, get_db
from app.db.url import prepare_asyncpg_database_url
from app.main import app
from app.models.subscription import SubscriptionPlan
from app.scripts.bootstrap import bootstrap

settings = get_settings()

# Use DATABASE_URL from the environment when supplied (CI/Docker). For direct Windows/Linux host
# test runs, default to local PostgreSQL instead of the Docker-only hostname `db`.
TEST_DATABASE_URL, TEST_CONNECT_ARGS = prepare_asyncpg_database_url(settings.database_url)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_test_database() -> None:
    # The local QA database may exist without any schema (for example after CREATE DATABASE).
    # Build the model schema before bootstrap queries module_definitions.  Guard against
    # accidentally running destructive/QA setup against a non-test database.
    database_name = settings.database_url.rsplit("/", 1)[-1].split("?", 1)[0].lower()
    if database_name != "schoolerp_test":
        raise RuntimeError(
            f"Refusing destructive pytest schema reset on database: {database_name!r}. "
            "Expected exactly 'schoolerp_test'."
        )
    async with app_engine.begin() as connection:
        # DROP SCHEMA ... CASCADE is intentional here: Base.metadata.drop_all()
        # cannot dependency-sort the legitimate circular FKs in the ERP model.
        await connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await connection.execute(text("CREATE SCHEMA public"))
        await connection.run_sync(Base.metadata.create_all)


@pytest_asyncio.fixture(scope="function")
async def bootstrap_test_database(prepare_test_database: None) -> None:
    await bootstrap()


@pytest_asyncio.fixture(scope="function")
async def admin_headers(client: AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login/json",
        json={
            "username": "superadmin",
            "password": settings.super_admin_password,
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, connect_args=TEST_CONNECT_ARGS)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session
        await session.rollback()

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(
    db_session: AsyncSession,
    bootstrap_test_database: None,
) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    class QAAsyncClient(AsyncClient):
        async def request(self, method: str, url, **kwargs):
            # Organization onboarding now requires a Plan/Trial. Older functional tests
            # intentionally focus on unrelated organization behavior and predate that
            # contract, and were written when every paid plan carried the full Phase-1
            # module catalog. Upgrade those legacy QA requests to the seeded
            # PREMIUM/yearly plan (all catalog modules) inside the test harness only, so
            # per-plan module entitlement (BASIC/STANDARD restrictions) stays exercised
            # solely by tests that opt into a specific plan explicitly.
            if method.upper() == "POST" and str(url).split("?", 1)[0].rstrip("/") == "/api/v1/organizations":
                payload = kwargs.get("json")
                if isinstance(payload, dict) and payload and "subscription_plan_id" not in payload:
                    premium = (
                        await db_session.execute(
                            select(SubscriptionPlan).where(SubscriptionPlan.code == "PREMIUM")
                        )
                    ).scalar_one_or_none()
                    assert premium is not None, "QA bootstrap must seed the PREMIUM subscription plan"
                    payload = dict(payload)
                    payload["subscription_plan_id"] = str(premium.id)
                    payload.setdefault("billing_cycle", "yearly")
                    kwargs["json"] = payload
            return await super().request(method, url, **kwargs)

    transport = ASGITransport(app=app)
    async with QAAsyncClient(
        transport=transport,
        base_url="http://test",
        headers={
            "X-Change-Confirmed": "true",
            "X-Change-Reason": "Automated QA test",
        },
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
