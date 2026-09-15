import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import (
    activate_school_for_qa,
    create_org,
    create_school,
)


TEST_PASSWORD = "QaTest@2026!Strong"
CHANGED_PASSWORD = "QaChanged@2026!Strong"


def suffix() -> str:
    return uuid.uuid4().hex[:8]


async def _login(
    client: AsyncClient,
    username: str,
    password: str,
    account_type: str,
) -> dict[str, str]:
    """
    Login with the supplied credentials and return bearer headers.
    """
    response = await client.post(
        "/api/v1/auth/login/json",
        json={
            "account_type": account_type,
            "username": username,
            "password": password,
        },
    )

    assert response.status_code == 200, response.text

    return {
        "Authorization": f"Bearer {response.json()['access_token']}"
    }


async def _complete_temporary_password_login(
    client: AsyncClient,
    username: str,
    temporary_password: str,
    account_type: str,
    *,
    new_password: str = CHANGED_PASSWORD,
) -> dict[str, str]:
    """
    Complete the mandatory first-login password-change workflow.

    Admin-created users receive a server-generated temporary password.
    They may authenticate with it, but normal ERP operations remain blocked
    until they replace it with a permanent password.

    Flow:
        temporary password login
        -> change own password
        -> login again with permanent password
        -> return normal bearer headers
    """

    temporary_headers = await _login(
        client,
        username,
        temporary_password,
        account_type,
    )

    change_response = await client.post(
        "/api/v1/auth/change-password",
        headers=temporary_headers,
        json={
            "current_password": temporary_password,
            "new_password": new_password,
        },
    )

    assert change_response.status_code == 204, change_response.text

    return await _login(
        client,
        username,
        new_password,
        account_type,
    )


@pytest.mark.asyncio
async def test_org_admin_and_school_admin_tenant_scopes(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
):
    token_a, token_b = suffix(), suffix()

    # ==============================================================
    # 1. CREATE TWO INDEPENDENT SOCIETY/TRUST ORGANIZATIONS
    # ==============================================================

    org_a = await create_org(
        client,
        admin_headers,
        name=f"AKSHARA {token_a}",
        allowed_schools=2,
        token=token_a,
    )

    org_b = await create_org(
        client,
        admin_headers,
        name=f"BHASHYAM {token_b}",
        allowed_schools=2,
        token=token_b,
    )

    # ==============================================================
    # 2. CREATE ONE SCHOOL UNDER EACH SOCIETY/TRUST
    # ==============================================================

    school_a = await create_school(
        client,
        admin_headers,
        org_a["id"],
        name="AKSHARA SCHOOL",
        area="Razole",
    )

    school_b = await create_school(
        client,
        admin_headers,
        org_b["id"],
        name="BHASHYAM SCHOOL",
        area="Razole",
    )

    # Paid Schools intentionally start in subscription/activation
    # pending state.
    #
    # This test validates tenant isolation rather than commercial
    # activation, so activate only School A through the QA-only helper.
    await activate_school_for_qa(
        db_session,
        school_a["id"],
    )

    # ==============================================================
    # 3. ORGANIZATION ADMIN FIRST-LOGIN PASSWORD FLOW
    # ==============================================================

    org_admin_username = f"orgadmin_{token_a.lower()}"

    org_temporary_password = org_a["temporary_password"]

    assert org_temporary_password

    # Organization Admin receives a generated temporary password during
    # Society/Trust creation. Complete the mandatory password change
    # before testing normal ERP operations.
    org_admin_headers = await _complete_temporary_password_login(
        client,
        org_admin_username,
        org_temporary_password,
        "ORGANIZATION_ADMIN",
        new_password=(
            f"OrgChanged@{token_a[:6]}2026!"
        ),
    )

    # ==============================================================
    # 4. ORGANIZATION ADMIN SCHOOL VISIBILITY
    # ==============================================================

    visible_schools = await client.get(
        "/api/v1/schools",
        headers=org_admin_headers,
    )

    assert visible_schools.status_code == 200, visible_schools.text

    visible_school_ids = {
        row["id"]
        for row in visible_schools.json()
    }

    assert visible_school_ids == {
        school_a["id"]
    }

    assert school_b["id"] not in visible_school_ids

    # ==============================================================
    # 5. ORGANIZATION ADMIN DASHBOARD
    # ==============================================================

    dashboard = await client.get(
        f"/api/v1/organizations/{org_a['id']}/dashboard",
        headers=org_admin_headers,
    )

    assert dashboard.status_code == 200, dashboard.text

    dashboard_payload = dashboard.json()

    assert dashboard_payload["unit_count"] == 1

    assert (
        dashboard_payload["units"][0]["school_id"]
        == school_a["id"]
    )

    assert dashboard_payload["today_collection"] == "0.00"
    assert dashboard_payload["outstanding_due"] == "0.00"
    assert dashboard_payload["overdue_due"] == "0.00"

    assert dashboard_payload["student_attendance_present"] == 0
    assert dashboard_payload["student_attendance_marked"] == 0

    assert dashboard_payload["teacher_attendance_present"] == 0
    assert dashboard_payload["teacher_attendance_marked"] == 0

    # ==============================================================
    # 6. ORGANIZATION ADMIN CANNOT ACCESS ANOTHER ORGANIZATION
    # ==============================================================

    forbidden_dashboard = await client.get(
        f"/api/v1/organizations/{org_b['id']}/dashboard",
        headers=org_admin_headers,
    )

    assert forbidden_dashboard.status_code == 403

    forbidden_school = await client.get(
        f"/api/v1/schools/{school_b['id']}",
        headers=org_admin_headers,
    )

    assert forbidden_school.status_code == 403

    # ==============================================================
    # 7. CREATE SCHOOL ADMIN
    # ==============================================================

    school_admin_username = (
        f"schooladmin_{token_a.lower()}"
    )

    create_school_admin = await client.post(
        "/api/v1/users",
        headers=org_admin_headers,
        json={
            "username": school_admin_username,

            # Kept because the current request schema accepts/requires it.
            # The server-generated temporary password remains authoritative
            # for the admin-created-user workflow.
            "password": TEST_PASSWORD,

            "full_name": "Razole Branch Administrator",
            "designation": "Principal",
            "account_type": "SCHOOL_ADMIN",

            "email": (
                f"shared.office.{token_a.lower()}"
                "@example.com"
            ),

            # Mandatory for School-level users.
            "phone": (
                f"9{int(token_a[:7], 16) % 1000000000:09d}"
            ),

            "organization_id": org_a["id"],
            "school_id": school_a["id"],
        },
    )

    assert (
        create_school_admin.status_code == 201
    ), create_school_admin.text

    school_admin_payload = create_school_admin.json()

    # ==============================================================
    # 8. VALIDATE GENERATED TEMPORARY CREDENTIAL
    # ==============================================================

    assert (
        school_admin_payload["username"].lower()
        == school_admin_username.lower()
    )

    school_admin_temporary_password = (
        school_admin_payload.get("temporary_password")
    )

    assert school_admin_temporary_password, (
        "School Admin creation must return the server-generated "
        "temporary password to the authorized Organization Admin"
    )

    assert isinstance(
        school_admin_temporary_password,
        str,
    )

    assert len(
        school_admin_temporary_password
    ) >= 10

    # ==============================================================
    # 9. SCHOOL ADMIN FIRST-LOGIN PASSWORD FLOW
    # ==============================================================

    school_admin_headers = (
        await _complete_temporary_password_login(
            client,
            school_admin_username,
            school_admin_temporary_password,
            "SCHOOL_ADMIN",
            new_password=(
                f"SchoolChanged@{token_a[:6]}2026!"
            ),
        )
    )

    # ==============================================================
    # 10. VERIFY SCHOOL ADMIN IDENTITY
    # ==============================================================

    school_admin_me = await client.get(
        "/api/v1/auth/me",
        headers=school_admin_headers,
    )

    assert (
        school_admin_me.status_code == 200
    ), school_admin_me.text

    school_admin_identity = school_admin_me.json()

    assert (
        school_admin_identity["account_type"]
        == "SCHOOL_ADMIN"
    )

    assert (
        school_admin_identity["organization_id"]
        == org_a["id"]
    )

    assert (
        school_admin_identity["school_id"]
        == school_a["id"]
    )

    # Campus has been removed as an operational authorization scope.
    # A legacy compatibility field may remain in API output, but it must
    # not expose an operational Campus assignment.
    if "campus_id" in school_admin_identity:
        assert school_admin_identity["campus_id"] is None

    # ==============================================================
    # 11. SCHOOL ADMIN SCHOOL VISIBILITY
    # ==============================================================

    school_admin_schools = await client.get(
        "/api/v1/schools",
        headers=school_admin_headers,
    )

    assert (
        school_admin_schools.status_code == 200
    ), school_admin_schools.text

    school_admin_visible_ids = {
        row["id"]
        for row in school_admin_schools.json()
    }

    assert school_admin_visible_ids == {
        school_a["id"]
    }

    assert (
        school_b["id"]
        not in school_admin_visible_ids
    )

    # ==============================================================
    # 12. SCHOOL ADMIN CANNOT ACCESS ANOTHER SCHOOL
    # ==============================================================

    school_admin_forbidden_school = await client.get(
        f"/api/v1/schools/{school_b['id']}",
        headers=school_admin_headers,
    )

    assert (
        school_admin_forbidden_school.status_code
        == 403
    )

    # ==============================================================
    # 13. SCHOOL ADMIN CANNOT ACCESS ANOTHER ORGANIZATION DASHBOARD
    # ==============================================================

    school_admin_forbidden_dashboard = await client.get(
        f"/api/v1/organizations/{org_b['id']}/dashboard",
        headers=school_admin_headers,
    )

    assert (
        school_admin_forbidden_dashboard.status_code
        == 403
    )