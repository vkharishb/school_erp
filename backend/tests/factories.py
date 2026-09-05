from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient

TEST_PASSWORD = "QaTest@2026!Strong"


def suffix() -> str:
    return uuid4().hex[:8].upper()


async def create_org(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    name: str | None = None,
    allowed_schools: int = 3,
    token: str | None = None,
) -> dict:
    token = token or suffix()
    response = await client.post(
        "/api/v1/organizations",
        headers=headers,
        json={
            "name": name or f"AKSHARA {token}",
            "allowed_schools": allowed_schools,
            "head_full_name": f"Organization Head {token}",
            "head_email": f"head.{token.lower()}@example.com",
            "head_phone": f"9000{int(token[:6], 16) % 1000000:06d}",
            "admin_username": f"orgadmin_{token.lower()}",
            "admin_email": f"admin.{token.lower()}@example.com",
            "admin_password": TEST_PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_school(
    client: AsyncClient,
    headers: dict[str, str],
    organization_id: str,
    *,
    name: str = "AKSHARA SCHOOL",
    area: str = "Razole",
    area_code: str | None = None,
    udise_codes: list[dict] | None = None,
) -> dict:
    configuration = {
        "name": name,
        "short_name": name[:40],
        "area": area,
        "city": area,
        "state": "Andhra Pradesh",
        "country": "India",
    }
    if area_code:
        configuration["area_code"] = area_code
    response = await client.post(
        "/api/v1/schools",
        headers=headers,
        json={
            "organization_id": organization_id,
            "configuration": configuration,
            "udise_codes": udise_codes or [],
            "enabled_modules": [
                "dashboard",
                "school_admin",
                "school_config",
                "student",
                "teacher",
                "fee",
                "attendance",
                "marks",
                "reports",
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def main_campus_id(client: AsyncClient, headers: dict[str, str], school_id: str) -> str:
    response = await client.get(f"/api/v1/foundation/schools/{school_id}/campuses", headers=headers)
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["code"] == "MAIN"
    return rows[0]["id"]


async def create_org_year(
    client: AsyncClient,
    headers: dict[str, str],
    organization_id: str,
    *,
    code: str = "2026-27",
    starts_on: str = "2026-06-01",
    ends_on: str = "2027-05-31",
    activate: bool = True,
) -> dict:
    response = await client.post(
        f"/api/v1/organizations/{organization_id}/academic-years",
        headers=headers,
        json={
            "code": code,
            "name": f"Academic Year {code}",
            "starts_on": starts_on,
            "ends_on": ends_on,
        },
    )
    assert response.status_code == 201, response.text
    row = response.json()
    if activate:
        activated = await client.post(
            f"/api/v1/organizations/academic-years/{row['id']}/activate",
            headers=headers,
        )
        assert activated.status_code == 200, activated.text
        row = activated.json()
    return row
