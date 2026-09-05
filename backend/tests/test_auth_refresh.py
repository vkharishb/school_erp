import pytest
from httpx import AsyncClient

from app.core.config import get_settings

settings = get_settings()


@pytest.mark.asyncio
async def test_refresh_cookie_rotation_and_replay_protection(client: AsyncClient):
    login = await client.post(
        "/api/v1/auth/login/json",
        json={"username": "superadmin", "password": settings.super_admin_password},
    )
    assert login.status_code == 200, login.text
    original = client.cookies.get(settings.refresh_cookie_name)
    assert original

    rotated = await client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["access_token"]
    assert "refresh_token" not in rotated.json()
    replacement = client.cookies.get(settings.refresh_cookie_name)
    assert replacement and replacement != original

    # Replay the already-rotated cookie. Reuse must revoke the whole family.
    client.cookies.set(settings.refresh_cookie_name, original, path="/api/v1/auth")
    replay = await client.post("/api/v1/auth/refresh")
    assert replay.status_code == 401
    assert replay.json()["error"]["message"] == "Refresh token reuse detected"

    client.cookies.set(settings.refresh_cookie_name, replacement, path="/api/v1/auth")
    family_revoked = await client.post("/api/v1/auth/refresh")
    assert family_revoked.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_the_access_session(client: AsyncClient):
    login = await client.post(
        "/api/v1/auth/login/json",
        json={"username": "superadmin", "password": settings.super_admin_password},
    )
    token = login.json()["access_token"]
    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    current_user = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert current_user.status_code == 401
