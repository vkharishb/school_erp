from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.license import SchoolLicense
from app.models.school import School
from app.models.subscription import SchoolSubscription

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

    # Finalized Society/Trust contract:
    # Admin Contact Email is also the Organization Admin login email.
    admin_email = f"admin.{token.lower()}@example.com"

    response = await client.post(
        "/api/v1/organizations",
        headers=headers,
        json={
            "name": name or f"AKSHARA {token}",
            "allowed_schools": allowed_schools,
            "head_full_name": f"Organization Head {token}",
            "head_email": admin_email,
            "head_phone": f"9000{int(token[:6], 16) % 1000000:06d}",
            "admin_username": f"orgadmin_{token.lower()}",
            "admin_email": admin_email,
            "admin_password": TEST_PASSWORD,
            "admin_designation": "Administrator",

            # Legacy tests are currently assigned a paid PREMIUM plan
            # by the test compatibility layer. Paid plans require
            # Payment Due Date.
            "payment_due_at": (
                datetime.now(timezone.utc) + timedelta(days=30)
            ).isoformat(),
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
    code_token = suffix()[:6]
    configuration = {
        "name": name,
        "short_name": f"SCH{code_token}",
        "area": area,
        "area_code": area_code or f"V{code_token}",
        "board": "State Board",
        "email": f"school.{code_token.lower()}@example.com",
        "phone": f"9100{int(code_token, 16) % 1000000:06d}",
        "address_line1": f"1 School Road, {area}",
        "city": area,
        "district": "Test District",
        "state": "Andhra Pradesh",
        "country": "India",
        "pincode": "533242",
    }

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


async def activate_school_for_qa(db: AsyncSession, school_id: str) -> None:
    """Explicitly activate a paid School for legacy operational tests.

    This helper is test-only. Production paid Schools must still complete the
    governed MAP + activation-key + Organization Admin activation workflow.
    """
    school = await db.get(School, school_id)
    assert school is not None
    school.is_active = True
    entitlement = (
        await db.execute(
            select(SchoolSubscription)
            .where(SchoolSubscription.school_id == school.id)
            .order_by(SchoolSubscription.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if entitlement is not None and entitlement.status != "trial":
        entitlement.status = "active"
    license_ = (
        await db.execute(select(SchoolLicense).where(SchoolLicense.school_id == school.id))
    ).scalar_one_or_none()
    if license_ is not None:
        license_.is_active = True
    await db.flush()


async def main_campus_id(
    client: AsyncClient,
    headers: dict[str, str],
    school_id: str,
) -> str:
    response = await client.get(
        f"/api/v1/foundation/schools/{school_id}/campuses",
        headers=headers,
    )
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