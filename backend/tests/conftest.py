import os

os.environ["APP_ENV"] = "test"
os.environ.setdefault("SECRET_KEY", "test-signing-key-for-automated-tests-only-1234567890")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://schoolerp:test-only@db:5432/schoolerp_test"
)
os.environ.setdefault("SUPER_ADMIN_USERNAME", "superadmin")
os.environ.setdefault("SUPER_ADMIN_EMAIL", "superadmin@schoolerp.test")
os.environ.setdefault("SUPER_ADMIN_PASSWORD", "QaTest@2026!Strong")

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.session import get_db
from app.db.url import prepare_asyncpg_database_url
from app.main import app
from app.scripts.bootstrap import bootstrap

settings = get_settings()

# Use the DATABASE_URL from env (set by CT workflow to the test DB)
TEST_DATABASE_URL, TEST_CONNECT_ARGS = prepare_asyncpg_database_url(settings.database_url)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def bootstrap_test_database() -> None:
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

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={
            "X-Change-Confirmed": "true",
            "X-Change-Reason": "Automated QA test",
        },
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
