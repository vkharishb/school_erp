from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import (
    TEST_PASSWORD,
    activate_school_for_qa,
    create_org,
    create_org_year,
    create_school,
    suffix,
)


async def _login(
    client: AsyncClient,
    login_id: str,
    password: str,
    account_type: str,
) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login/json",
        json={
            "account_type": account_type,
            "username": login_id,
            "password": password,
        },
    )
    assert response.status_code == 200, response.text

    headers = {
        "Authorization": f"Bearer {response.json()['access_token']}"
    }

    me = await client.get(
        "/api/v1/auth/me",
        headers=headers,
    )
    assert me.status_code == 200, me.text

    if me.json().get("must_change_password"):
        changed_password = "QaChanged@2026!Strong"

        changed = await client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={
                "current_password": password,
                "new_password": changed_password,
            },
        )
        assert changed.status_code == 204, changed.text

        response = await client.post(
            "/api/v1/auth/login/json",
            json={
                "account_type": account_type,
                "username": login_id,
                "password": changed_password,
            },
        )
        assert response.status_code == 200, response.text

        headers = {
            "Authorization": (
                f"Bearer {response.json()['access_token']}"
            )
        }

    return headers


@pytest.mark.asyncio
async def test_org_school_limit_annual_correction_and_super_admin_override(
    client: AsyncClient,
    admin_headers: dict[str, str],
):
    token = suffix()

    org = await create_org(
        client,
        admin_headers,
        name=f"AKSHARA SCHOOL {token}",
        allowed_schools=1,
        token=token,
    )

    assert org["allowed_schools"] == 1
    assert org["head_full_name"].startswith("Organization Head")

    await create_org_year(
        client,
        admin_headers,
        org["id"],
        activate=True,
    )

    org_admin_headers = await _login(
        client,
        f"orgadmin_{token.lower()}",
        org["temporary_password"],
        "ORGANIZATION_ADMIN",
    )

    first_school = await create_school(
        client,
        admin_headers,
        org["id"],
        name="AKSHARA SCHOOL",
        area="Razole",
    )

    assert first_school["code"].startswith("AK-RZL-")

    # School creation is a Platform Owner-only commercial/governance
    # action.
    over_limit = await client.post(
        "/api/v1/schools",
        headers=org_admin_headers,
        json={
            "organization_id": org["id"],
            "configuration": {
                "name": "AKSHARA SCHOOL",
                "short_name": "AKS",
                "area": "Pedana",
                "area_code": "PED",
                "board": "State Board",
                "email": "aks.pedana@example.com",
                "phone": "9876543210",
                "address_line1": "1 School Road",
                "city": "Pedana",
                "district": "Krishna",
                "state": "Andhra Pradesh",
                "pincode": "521366",
            },
            "udise_codes": [],
        },
    )

    assert over_limit.status_code == 403, over_limit.text

    # Platform Owner must update subscribed School count before
    # adding another School.
    platform_over_limit = await client.post(
        "/api/v1/schools",
        headers=admin_headers,
        json={
            "organization_id": org["id"],
            "configuration": {
                "name": "AKSHARA SCHOOL",
                "short_name": "AKS",
                "area": "Pedana",
                "area_code": "PED",
                "board": "State Board",
                "email": "aks.pedana@example.com",
                "phone": "9876543210",
                "address_line1": "1 School Road",
                "city": "Pedana",
                "district": "Krishna",
                "state": "Andhra Pradesh",
                "pincode": "521366",
            },
            "udise_codes": [],
        },
    )

    assert (
        platform_over_limit.status_code == 409
    ), platform_over_limit.text

    assert "School limit reached" in platform_over_limit.text

    # One client Organization correction per active Academic Year.
    first_correction = await client.patch(
        f"/api/v1/organizations/{org['id']}",
        headers={
            **org_admin_headers,
            "X-Change-Reason": "Correct Organization Head phone",
        },
        json={
            "head_phone": "9876543210",
        },
    )

    assert (
        first_correction.status_code == 200
    ), first_correction.text

    second_correction = await client.patch(
        f"/api/v1/organizations/{org['id']}",
        headers={
            **org_admin_headers,
            "X-Change-Reason": "Second client correction attempt",
        },
        json={
            "head_phone": "9876543211",
        },
    )

    assert (
        second_correction.status_code == 409
    ), second_correction.text

    assert "already been used" in second_correction.text

    # Platform Owner can increase agreed School count.
    super_override = await client.patch(
        f"/api/v1/organizations/{org['id']}",
        headers={
            **admin_headers,
            "X-Change-Reason": (
                "Platform Owner approved additional School capacity"
            ),
        },
        json={
            "allowed_schools": 3,
            "head_phone": "9876543212",
            "capacity_effective_at": (
                datetime.now(timezone.utc).isoformat()
            ),
            "capacity_reason": (
                "Platform Owner approved additional School capacity"
            ),
        },
    )

    assert (
        super_override.status_code == 200
    ), super_override.text

    assert super_override.json()["allowed_schools"] == 3


@pytest.mark.asyncio
async def test_user_email_can_repeat_but_username_and_account_type_are_controlled(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
):
    token = suffix()

    org = await create_org(
        client,
        admin_headers,
        name=f"User Group {token}",
        allowed_schools=1,
        token=token,
    )

    school = await create_school(
        client,
        admin_headers,
        org["id"],
        name="AKSHARA SCHOOL",
        area="Razole",
    )

    await activate_school_for_qa(
        db_session,
        school["id"],
    )

    org_admin_headers = await _login(
        client,
        f"orgadmin_{token.lower()}",
        org["temporary_password"],
        "ORGANIZATION_ADMIN",
    )

    shared_email = (
        f"office.{token.lower()}@example.com"
    )

    for account_type, username in (
        (
            "SCHOOL_ADMIN",
            f"school_{token.lower()}",
        ),
        (
            "ACCOUNTS",
            f"accounts_{token.lower()}",
        ),
    ):
        created = await client.post(
            "/api/v1/users",
            headers=org_admin_headers,
            json={
                "username": username,
                "password": TEST_PASSWORD,
                "full_name": f"{account_type} User",
                "account_type": account_type,
                "email": shared_email,
                "phone": (
                    f"9{int(token[:7], 16) % 1000000000:09d}"
                ),
                "organization_id": org["id"],
                "school_id": school["id"],
            },
        )

        assert created.status_code == 201, created.text
        assert created.json()["email"] == shared_email

    duplicate_username = await client.post(
        "/api/v1/users",
        headers=org_admin_headers,
        json={
            "username": f"accounts_{token.lower()}",
            "password": TEST_PASSWORD,
            "full_name": "Duplicate Username",
            "account_type": "TEACHER",
            "email": shared_email,
            "phone": (
                f"9{int(token[:7], 16) % 1000000000:09d}"
            ),
            "organization_id": org["id"],
            "school_id": school["id"],
        },
    )

    assert (
        duplicate_username.status_code == 409
    ), duplicate_username.text

    mismatch_login = await client.post(
        "/api/v1/auth/login/json",
        json={
            "account_type": "TEACHER",
            "username": f"accounts_{token.lower()}",
            "password": TEST_PASSWORD,
        },
    )

    assert mismatch_login.status_code == 401

    assert (
        "Invalid account type or login credentials"
        in mismatch_login.text
    )


@pytest.mark.asyncio
async def test_super_admin_can_update_school_profile_with_udise_without_async_lazy_load(
    client: AsyncClient,
    admin_headers: dict[str, str],
):
    token = suffix()

    org = await create_org(
        client,
        admin_headers,
        name=f"Profile Group {token}",
        allowed_schools=1,
        token=token,
    )

    udise = (
        f"28{int(token, 16) % 100000000:08d}"
    )

    school = await create_school(
        client,
        admin_headers,
        org["id"],
        name="AKSHARA SCHOOL",
        area="Razole",
        udise_codes=[
            {
                "udise_code": udise,
                "label": "Primary",
                "is_primary": True,
            }
        ],
    )

    response = await client.patch(
        f"/api/v1/schools/{school['id']}/profile",
        headers={
            **admin_headers,
            "X-Change-Reason": (
                "Correct School profile information"
            ),
        },
        json={
            "configuration": {
                "tagline": "Educating for the future",
            },
            "udise_codes": [
                {
                    "udise_code": udise,
                    "label": "Primary",
                    "is_primary": True,
                }
            ],
        },
    )

    assert response.status_code == 200, response.text

    body = response.json()

    assert (
        body["configuration"]["tagline"]
        == "Educating for the future"
    )

    assert (
        body["udise_codes"][0]["udise_code"]
        == udise
    )


@pytest.mark.asyncio
async def test_staff_username_login_and_uniqueness_are_case_insensitive(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
):
    token = suffix()

    org = await create_org(
        client,
        admin_headers,
        name=f"Case Login {token}",
        allowed_schools=1,
        token=token,
    )

    login = await client.post(
        "/api/v1/auth/login/json",
        json={
            "account_type": "ORGANIZATION_ADMIN",
            "username": f"ORGADMIN_{token}",
            "password": org["temporary_password"],
        },
    )

    assert login.status_code == 200, login.text

    school = await create_school(
        client,
        admin_headers,
        org["id"],
        name="AKSHARA SCHOOL",
        area="Razole",
    )

    await activate_school_for_qa(
        db_session,
        school["id"],
    )

    first = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "username": f"Teacher_{token}",
            "password": TEST_PASSWORD,
            "full_name": "Case Teacher",
            "account_type": "TEACHER",
            "email": (
                f"case.teacher.{token.lower()}@example.com"
            ),
            "phone": (
                f"9{int(token[:7], 16) % 1000000000:09d}"
            ),
            "organization_id": org["id"],
            "school_id": school["id"],
        },
    )

    assert first.status_code == 201, first.text

    assert (
        first.json()["username"]
        == f"teacher_{token.lower()}"
    )

    duplicate = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "username": f"TEACHER_{token}",
            "password": TEST_PASSWORD,
            "full_name": "Duplicate Case Teacher",
            "account_type": "TEACHER",
            "email": (
                f"duplicate.case.teacher."
                f"{token.lower()}@example.com"
            ),
            "phone": (
                f"9{int(token[:7], 16) % 1000000000:09d}"
            ),
            "organization_id": org["id"],
            "school_id": school["id"],
        },
    )

    assert duplicate.status_code == 409, duplicate.text


@pytest.mark.asyncio
async def test_password_reset_is_admin_only_and_hierarchy_is_enforced(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
):
    token = suffix()

    org = await create_org(
        client,
        admin_headers,
        name=f"Reset Group {token}",
        allowed_schools=1,
        token=token,
    )

    school = await create_school(
        client,
        admin_headers,
        org["id"],
        name="AKSHARA SCHOOL",
        area="Razole",
    )

    await activate_school_for_qa(
        db_session,
        school["id"],
    )

    org_admin_headers = await _login(
        client,
        f"orgadmin_{token.lower()}",
        org["temporary_password"],
        "ORGANIZATION_ADMIN",
    )

    # ----------------------------------------------------------
    # Create School Admin
    # ----------------------------------------------------------

    school_admin = await client.post(
        "/api/v1/users",
        headers=org_admin_headers,
        json={
            "username": f"schooladmin_{token}",
            "password": TEST_PASSWORD,
            "full_name": "School Admin",
            "designation": "Principal",
            "account_type": "SCHOOL_ADMIN",
            "email": (
                f"schooladmin.{token.lower()}@example.com"
            ),
            "phone": (
                f"9{int(token[:7], 16) % 1000000000:09d}"
            ),
            "organization_id": org["id"],
            "school_id": school["id"],
        },
    )

    assert (
        school_admin.status_code == 201
    ), school_admin.text

    # ----------------------------------------------------------
    # Create Teacher
    # ----------------------------------------------------------

    teacher = await client.post(
        "/api/v1/users",
        headers=org_admin_headers,
        json={
            "username": f"teacher_{token}",
            "password": TEST_PASSWORD,
            "full_name": "Teacher User",
            "account_type": "TEACHER",
            "email": (
                f"teacher.{token.lower()}@example.com"
            ),
            "phone": (
                f"8{int(token[:7], 16) % 1000000000:09d}"
            ),
            "organization_id": org["id"],
            "school_id": school["id"],
        },
    )

    assert teacher.status_code == 201, teacher.text

    teacher_payload = teacher.json()

    original_teacher_temporary_password = (
        teacher_payload.get("temporary_password")
    )

    assert original_teacher_temporary_password

    # ----------------------------------------------------------
    # Organization Admin may reset a lower-level School user.
    #
    # Password reset now generates a server-side temporary
    # password and returns it to the authorized administrator.
    # ----------------------------------------------------------

    reset_teacher = await client.post(
        (
            f"/api/v1/users/"
            f"{teacher_payload['id']}/reset-password"
        ),
        headers=org_admin_headers,
        json={
            "new_password": "ResetTeacher@2026!",
        },
    )

    assert (
        reset_teacher.status_code == 200
    ), reset_teacher.text

    reset_teacher_payload = reset_teacher.json()

    assert (
        reset_teacher_payload["username"].lower()
        == f"teacher_{token}".lower()
    )

    teacher_reset_temporary_password = (
        reset_teacher_payload.get("temporary_password")
    )

    assert teacher_reset_temporary_password, (
        "Authorized Organization Admin password reset must "
        "return a server-generated temporary password"
    )

    assert isinstance(
        teacher_reset_temporary_password,
        str,
    )

    assert len(
        teacher_reset_temporary_password
    ) >= 10

    assert (
        teacher_reset_temporary_password
        != original_teacher_temporary_password
    )

    # ----------------------------------------------------------
    # Platform Owner may reset Organization Admin.
    # ----------------------------------------------------------

    org_users = await client.get(
        "/api/v1/users",
        headers=admin_headers,
        params={
            "organization_id": org["id"],
        },
    )

    assert org_users.status_code == 200, org_users.text

    org_admin = next(
        user
        for user in org_users.json()
        if user["account_type"] == "ORGANIZATION_ADMIN"
    )

    # A School-scoped Platform Owner view includes the Organization
    # Admin governing the School.
    platform_school_users = await client.get(
        "/api/v1/users",
        headers=admin_headers,
        params={
            "school_id": school["id"],
            "include_organization_admins": True,
        },
    )

    assert (
        platform_school_users.status_code == 200
    ), platform_school_users.text

    assert org_admin["id"] in {
        user["id"]
        for user in platform_school_users.json()
    }

    # Lower-level actors cannot opt into Platform Owner hierarchy
    # view.
    denied_hierarchy_view = await client.get(
        "/api/v1/users",
        headers=org_admin_headers,
        params={
            "school_id": school["id"],
            "include_organization_admins": True,
        },
    )

    assert (
        denied_hierarchy_view.status_code == 403
    ), denied_hierarchy_view.text

    # ----------------------------------------------------------
    # Platform Owner resets Organization Admin.
    # ----------------------------------------------------------

    reset_org_admin = await client.post(
        (
            f"/api/v1/users/"
            f"{org_admin['id']}/reset-password"
        ),
        headers=admin_headers,
        json={
            "new_password": "ResetOrgAdmin@2026!",
        },
    )

    assert (
        reset_org_admin.status_code == 200
    ), reset_org_admin.text

    reset_org_admin_payload = reset_org_admin.json()

    assert (
        reset_org_admin_payload["username"].lower()
        == f"orgadmin_{token.lower()}".lower()
    )

    org_admin_reset_temporary_password = (
        reset_org_admin_payload.get("temporary_password")
    )

    assert org_admin_reset_temporary_password, (
        "Platform Owner password reset must return the "
        "server-generated temporary password"
    )

    assert isinstance(
        org_admin_reset_temporary_password,
        str,
    )

    assert len(
        org_admin_reset_temporary_password
    ) >= 10

    # ----------------------------------------------------------
    # Teacher must authenticate with the generated reset
    # temporary password, not the client-provided password.
    # ----------------------------------------------------------

    teacher_login = await client.post(
        "/api/v1/auth/login/json",
        json={
            "account_type": "TEACHER",
            "username": f"TEACHER_{token}",
            "password": teacher_reset_temporary_password,
        },
    )

    assert (
        teacher_login.status_code == 200
    ), teacher_login.text

    teacher_headers = {
        "Authorization": (
            f"Bearer {teacher_login.json()['access_token']}"
        )
    }

    # ----------------------------------------------------------
    # Temporary-password security gate
    # ----------------------------------------------------------
    #
    # Teacher has just received a reset temporary password.
    # Normal ERP operations may therefore be blocked until the
    # Teacher changes the password.
    #
    # Complete the mandatory password-change flow before testing
    # the actual School-scope authorization behavior.
    # ----------------------------------------------------------

    teacher_new_password = (
        f"TeacherChanged@{token[:6]}2026!"
    )

    teacher_change_password = await client.post(
        "/api/v1/auth/change-password",
        headers=teacher_headers,
        json={
            "current_password": (
                teacher_reset_temporary_password
            ),
            "new_password": teacher_new_password,
        },
    )

    assert (
        teacher_change_password.status_code == 204
    ), teacher_change_password.text

    # Login again with permanent password.
    teacher_login = await client.post(
        "/api/v1/auth/login/json",
        json={
            "account_type": "TEACHER",
            "username": f"TEACHER_{token}",
            "password": teacher_new_password,
        },
    )

    assert (
        teacher_login.status_code == 200
    ), teacher_login.text

    teacher_headers = {
        "Authorization": (
            f"Bearer {teacher_login.json()['access_token']}"
        )
    }

    # ----------------------------------------------------------
    # Teacher School scope does not require operational Campus
    # scope.
    #
    # Existing campus-backed academic data remains readable for
    # compatibility without assigning Campus as authorization
    # scope.
    # ----------------------------------------------------------

    teacher_campuses = await client.get(
        (
            f"/api/v1/foundation/schools/"
            f"{school['id']}/campuses"
        ),
        headers=teacher_headers,
    )

    assert (
        teacher_campuses.status_code == 200
    ), teacher_campuses.text

    assert teacher_campuses.json(), (
        "School-scoped Teacher should see the School campus "
        "catalogue"
    )

    # ----------------------------------------------------------
    # Functional users cannot obtain administrative reset
    # capability even if they know another user's ID.
    # ----------------------------------------------------------

    denied = await client.post(
        (
            f"/api/v1/users/"
            f"{school_admin.json()['id']}/reset-password"
        ),
        headers=teacher_headers,
        json={
            "new_password": "ShouldNeverApply@2026!",
        },
    )

    assert denied.status_code == 403, denied.text