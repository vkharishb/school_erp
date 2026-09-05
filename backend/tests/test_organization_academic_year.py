import pytest
from httpx import AsyncClient

from tests.factories import create_org, create_school, main_campus_id, suffix


@pytest.mark.asyncio
async def test_organization_academic_year_is_single_source_and_projects_to_all_schools(
    client: AsyncClient,
    admin_headers: dict[str, str],
):
    token = suffix()
    org = await create_org(
        client, admin_headers, name=f"Academic Group {token}", allowed_schools=2, token=token
    )
    organization_id = org["id"]

    campus_ids = []
    for index, area in enumerate(("Razole", "Pedana"), start=1):
        school = await create_school(
            client,
            admin_headers,
            organization_id,
            name=f"Academic School {token}",
            area=area,
        )
        campus_ids.append(await main_campus_id(client, admin_headers, school["id"]))

    create_year = await client.post(
        f"/api/v1/organizations/{organization_id}/academic-years",
        headers=admin_headers,
        json={
            "code": "2026-27",
            "name": "Academic Year 2026-27",
            "starts_on": "2026-06-01",
            "ends_on": "2027-05-31",
        },
    )
    assert create_year.status_code == 201, create_year.text

    duplicate = await client.post(
        f"/api/v1/organizations/{organization_id}/academic-years",
        headers=admin_headers,
        json={
            "code": "2026-27",
            "name": "Duplicate label is not allowed to duplicate the code",
            "starts_on": "2026-06-01",
            "ends_on": "2027-05-31",
        },
    )
    assert duplicate.status_code == 409, duplicate.text

    activate = await client.post(
        f"/api/v1/organizations/academic-years/{create_year.json()['id']}/activate",
        headers=admin_headers,
    )
    assert activate.status_code == 200, activate.text
    assert activate.json()["status"] == "active"

    org_years = await client.get(
        f"/api/v1/organizations/{organization_id}/academic-years",
        headers=admin_headers,
    )
    assert org_years.status_code == 200, org_years.text
    assert [row["code"] for row in org_years.json()].count("2026-27") == 1

    for campus_id in campus_ids:
        years = await client.get(
            f"/api/v1/foundation/campuses/{campus_id}/academic-years",
            headers=admin_headers,
        )
        assert years.status_code == 200, years.text
        matching = [row for row in years.json() if row["code"] == "2026-27"]
        assert len(matching) == 1
        assert matching[0]["starts_on"] == "2026-06-01"
        assert matching[0]["ends_on"] == "2027-05-31"
        assert matching[0]["status"] == "active"
