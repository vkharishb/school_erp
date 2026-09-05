import pytest
from httpx import AsyncClient

from tests.factories import create_org, create_school, main_campus_id, suffix


@pytest.mark.asyncio
async def test_school_level_academic_year_writes_are_blocked(
    client: AsyncClient, admin_headers: dict[str, str]
):
    token = suffix()
    org = await create_org(
        client, admin_headers, name=f"School AY Group {token}", allowed_schools=1, token=token
    )
    school = await create_school(
        client, admin_headers, org["id"], name="AKSHARA SCHOOL", area="Razole"
    )
    campus_id = await main_campus_id(client, admin_headers, school["id"])

    direct_school_year = await client.post(
        f"/api/v1/foundation/campuses/{campus_id}/academic-years",
        headers=admin_headers,
        json={
            "code": "2026-27",
            "name": "Academic Year 2026-27",
            "starts_on": "2026-06-01",
            "ends_on": "2027-05-31",
        },
    )
    assert direct_school_year.status_code == 409, direct_school_year.text
    assert "organization-wide" in direct_school_year.text

    organization_year = await client.post(
        f"/api/v1/organizations/{org['id']}/academic-years",
        headers=admin_headers,
        json={
            "code": "2026-27",
            "name": "Academic Year 2026-27",
            "starts_on": "2026-06-01",
            "ends_on": "2027-05-31",
        },
    )
    assert organization_year.status_code == 201, organization_year.text

    campus_years = await client.get(
        f"/api/v1/foundation/campuses/{campus_id}/academic-years",
        headers=admin_headers,
    )
    assert campus_years.status_code == 200, campus_years.text
    assert len(campus_years.json()) == 1
    projected_year_id = campus_years.json()[0]["id"]

    direct_activate = await client.post(
        f"/api/v1/foundation/academic-years/{projected_year_id}/activate",
        headers=admin_headers,
    )
    assert direct_activate.status_code == 409, direct_activate.text
    assert "organization-wide" in direct_activate.text

    organization_activate = await client.post(
        f"/api/v1/organizations/academic-years/{organization_year.json()['id']}/activate",
        headers=admin_headers,
    )
    assert organization_activate.status_code == 200, organization_activate.text

    campus_years = await client.get(
        f"/api/v1/foundation/campuses/{campus_id}/academic-years",
        headers=admin_headers,
    )
    assert campus_years.json()[0]["status"] == "active"
