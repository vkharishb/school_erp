import pytest
from httpx import AsyncClient

from tests.factories import TEST_PASSWORD, create_org, create_school, suffix


async def _login(
    client: AsyncClient, username: str, password: str, account_type: str
) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login/json",
        json={"account_type": account_type, "username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    if me.json().get("must_change_password"):
        changed_password = "QaChanged@2026!Strong"
        changed = await client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={"current_password": password, "new_password": changed_password},
        )
        assert changed.status_code == 204, changed.text
        response = await client.post(
            "/api/v1/auth/login/json",
            json={"account_type": account_type, "username": username, "password": changed_password},
        )
        assert response.status_code == 200, response.text
        headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    return headers


@pytest.mark.asyncio
async def test_org_admin_and_school_admin_tenant_scopes(
    client: AsyncClient,
    admin_headers: dict[str, str],
):
    token_a, token_b = suffix(), suffix()
    org_a = await create_org(
        client, admin_headers, name=f"AKSHARA {token_a}", allowed_schools=2, token=token_a
    )
    org_b = await create_org(
        client, admin_headers, name=f"BHASHYAM {token_b}", allowed_schools=2, token=token_b
    )

    school_a = await create_school(
        client, admin_headers, org_a["id"], name="AKSHARA SCHOOL", area="Razole"
    )
    school_b = await create_school(
        client, admin_headers, org_b["id"], name="BHASHYAM SCHOOL", area="Razole"
    )

    org_admin_username = f"orgadmin_{token_a.lower()}"
    org_admin_headers = await _login(
        client, org_admin_username, TEST_PASSWORD, "ORGANIZATION_ADMIN"
    )

    visible_schools = await client.get("/api/v1/schools", headers=org_admin_headers)
    assert visible_schools.status_code == 200, visible_schools.text
    assert {row["id"] for row in visible_schools.json()} == {school_a["id"]}

    dashboard = await client.get(
        f"/api/v1/organizations/{org_a['id']}/dashboard",
        headers=org_admin_headers,
    )
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["unit_count"] == 1
    assert dashboard.json()["units"][0]["school_id"] == school_a["id"]
    assert dashboard.json()["today_collection"] == "0.00"
    assert dashboard.json()["outstanding_due"] == "0.00"
    assert dashboard.json()["overdue_due"] == "0.00"
    assert dashboard.json()["student_attendance_present"] == 0
    assert dashboard.json()["student_attendance_marked"] == 0
    assert dashboard.json()["teacher_attendance_present"] == 0
    assert dashboard.json()["teacher_attendance_marked"] == 0

    forbidden_dashboard = await client.get(
        f"/api/v1/organizations/{org_b['id']}/dashboard",
        headers=org_admin_headers,
    )
    assert forbidden_dashboard.status_code == 403

    forbidden_school = await client.get(
        f"/api/v1/schools/{school_b['id']}", headers=org_admin_headers
    )
    assert forbidden_school.status_code == 403

    school_admin_username = f"schooladmin_{token_a.lower()}"
    create_school_admin = await client.post(
        "/api/v1/users",
        headers=org_admin_headers,
        json={
            "username": school_admin_username,
            "password": TEST_PASSWORD,
            "full_name": "Razole Branch Administrator",
            "designation": "Principal",
            "account_type": "SCHOOL_ADMIN",
            "email": f"shared.office.{token_a.lower()}@example.com",
            "organization_id": org_a["id"],
            "school_id": school_a["id"],
        },
    )
    assert create_school_admin.status_code == 201, create_school_admin.text

    school_admin_headers = await _login(
        client, school_admin_username, TEST_PASSWORD, "SCHOOL_ADMIN"
    )
    school_admin_me = await client.get("/api/v1/auth/me", headers=school_admin_headers)
    assert school_admin_me.status_code == 200, school_admin_me.text
    assert set(school_admin_me.json()["enabled_modules"]) >= {
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

    # School Admin cannot use Organization-level management APIs.
    forbidden_organization = await client.get(
        f"/api/v1/organizations/{org_a['id']}", headers=school_admin_headers
    )
    assert forbidden_organization.status_code == 403

    own_school = await client.get(f"/api/v1/schools/{school_a['id']}", headers=school_admin_headers)
    assert own_school.status_code == 200, own_school.text

    forbidden_other_school = await client.get(
        f"/api/v1/schools/{school_b['id']}", headers=school_admin_headers
    )
    assert forbidden_other_school.status_code == 403
