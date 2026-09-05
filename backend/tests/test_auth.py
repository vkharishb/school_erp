import pytest
from httpx import AsyncClient

from app.core.config import get_settings

settings = get_settings()


@pytest.mark.asyncio
async def test_login_json_success_uses_http_only_refresh_cookie(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login/json",
        json={"username": "superadmin", "password": settings.super_admin_password},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" not in data
    assert data["token_type"] == "bearer"
    set_cookie = response.headers.get("set-cookie", "").lower()
    assert settings.refresh_cookie_name.lower() in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=strict" in set_cookie


@pytest.mark.asyncio
async def test_login_json_wrong_password(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login/json",
        json={"username": "superadmin", "password": "definitely-wrong-password"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_token(client: AsyncClient):
    login = await client.post(
        "/api/v1/auth/login/json",
        json={"username": "superadmin", "password": settings.super_admin_password},
    )
    token = login.json()["access_token"]
    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["is_superuser"] is True


@pytest.mark.asyncio
async def test_platform_owner_username_login_is_case_insensitive(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login/json",
        json={
            "account_type": "SUPER_ADMIN",
            "username": "SUPERADMIN",
            "password": settings.super_admin_password,
        },
    )
    assert response.status_code == 200, response.text
    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {response.json()['access_token']}"},
    )
    assert me.status_code == 200, me.text
    assert me.json()["is_superuser"] is True


@pytest.mark.asyncio
async def test_self_password_change_does_not_require_business_change_headers(client: AsyncClient):
    login = await client.post(
        "/api/v1/auth/login/json",
        json={
            "account_type": "SUPER_ADMIN",
            "username": "SUPERADMIN",
            "password": settings.super_admin_password,
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    new_password = "FreshPlatform@2026!"
    changed = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": settings.super_admin_password, "new_password": new_password},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Change-Confirmed": "",
            "X-Change-Reason": "",
        },
    )
    assert changed.status_code == 204, changed.text

    relogin = await client.post(
        "/api/v1/auth/login/json",
        json={
            "account_type": "SUPER_ADMIN",
            "username": "SuperAdmin",
            "password": new_password,
        },
    )
    assert relogin.status_code == 200, relogin.text


@pytest.mark.asyncio
async def test_platform_owner_legacy_account_type_is_canonicalized_on_login(
    client: AsyncClient, db_session
):
    from sqlalchemy import func, select

    from app.models.user import User

    result = await db_session.execute(
        select(User).where(func.lower(User.username) == "superadmin", User.is_superuser.is_(True))
    )
    owner = result.scalar_one()
    owner.account_type = "PLATFORM_SUPER_ADMIN"
    await db_session.flush()

    response = await client.post(
        "/api/v1/auth/login/json",
        json={
            "account_type": "SUPER_ADMIN",
            "username": "SuperAdmin",
            "password": settings.super_admin_password,
        },
    )
    assert response.status_code == 200, response.text

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {response.json()['access_token']}"},
    )
    assert me.status_code == 200, me.text
    assert me.json()["account_type"] == "SUPER_ADMIN"
