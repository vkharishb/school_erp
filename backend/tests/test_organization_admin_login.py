from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.factories import TEST_PASSWORD


@pytest.mark.asyncio
async def test_organization_admin_can_login_with_username_or_email(
    client: AsyncClient, admin_headers: dict[str, str]
):
    token = uuid4().hex[:8]
    username = f"orgadmin_{token}"
    email = f"admin.{token}@example.com"
    create = await client.post(
        "/api/v1/organizations",
        headers=admin_headers,
        json={
            "name": f"Dual Login Organization {token}",
            "allowed_schools": 2,
            "head_full_name": "Dual Login Admin",
            "head_email": f"head.{token}@example.com",
            "head_phone": "9000000000",
            "admin_username": username,
            "admin_email": email,
            "admin_password": TEST_PASSWORD,
        },
    )
    assert create.status_code == 201, create.text
    organization = create.json()
    assert organization["admin_username"] == username
    assert organization["admin_email"] == email

    for login_id in (username.upper(), email.upper()):
        login = await client.post(
            "/api/v1/auth/login/json",
            json={
                "account_type": "ORGANIZATION_ADMIN",
                "username": login_id,
                "password": TEST_PASSWORD,
            },
        )
        assert login.status_code == 200, login.text
        assert "access_token" in login.json()
        me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )
        assert me.status_code == 200, me.text
        assert set(me.json()["enabled_modules"]) >= {
            "dashboard",
            "school_admin",
            "school_config",
            "student",
            "teacher",
            "fee",
            "marks",
            "attendance",
            "reports",
        }

    listed = await client.get("/api/v1/organizations", headers=admin_headers)
    assert listed.status_code == 200, listed.text
    matching = next(row for row in listed.json() if row["id"] == organization["id"])
    assert matching["admin_username"] == username
    assert matching["admin_email"] == email


@pytest.mark.asyncio
async def test_organization_admin_email_must_be_unique(
    client: AsyncClient, admin_headers: dict[str, str]
):
    token = uuid4().hex[:8]
    email = f"unique.{token}@example.com"

    def payload(suffix: str) -> dict:
        return {
            "name": f"Email Uniqueness {suffix} {token}",
            "allowed_schools": 1,
            "head_full_name": f"Organization Head {suffix}",
            "head_email": f"head.{suffix}.{token}@example.com",
            "admin_username": f"orgadmin_{suffix}_{token}",
            "admin_email": email,
            "admin_password": TEST_PASSWORD,
        }

    first = await client.post("/api/v1/organizations", headers=admin_headers, json=payload("one"))
    assert first.status_code == 201, first.text
    second = await client.post("/api/v1/organizations", headers=admin_headers, json=payload("two"))
    assert second.status_code == 409, second.text
    assert "username or email already exists" in second.json()["error"]["message"].lower()
