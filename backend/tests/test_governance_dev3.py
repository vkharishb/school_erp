import pytest
from httpx import AsyncClient

from tests.factories import TEST_PASSWORD, create_org, create_org_year, create_school, suffix


async def _login(
    client: AsyncClient, login_id: str, password: str, account_type: str
) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login/json",
        json={"account_type": account_type, "username": login_id, "password": password},
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
            json={"account_type": account_type, "username": login_id, "password": changed_password},
        )
        assert response.status_code == 200, response.text
        headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    return headers


@pytest.mark.asyncio
async def test_org_school_limit_annual_correction_and_super_admin_override(
    client: AsyncClient, admin_headers: dict[str, str]
):
    token = suffix()
    org = await create_org(
        client, admin_headers, name=f"AKSHARA SCHOOL {token}", allowed_schools=1, token=token
    )
    assert org["allowed_schools"] == 1
    assert org["head_full_name"].startswith("Organization Head")

    await create_org_year(client, admin_headers, org["id"], activate=True)
    org_admin_headers = await _login(
        client, f"orgadmin_{token.lower()}", TEST_PASSWORD, "ORGANIZATION_ADMIN"
    )

    first_school = await create_school(
        client, org_admin_headers, org["id"], name="AKSHARA SCHOOL", area="Razole"
    )
    assert first_school["code"].startswith("AK-RZL-")

    # Organization Admin may not exceed the commercial School count.
    over_limit = await client.post(
        "/api/v1/schools",
        headers=org_admin_headers,
        json={
            "organization_id": org["id"],
            "configuration": {"name": "AKSHARA SCHOOL", "area": "Pedana"},
            "udise_codes": [],
        },
    )
    assert over_limit.status_code == 409, over_limit.text
    assert "School limit reached" in over_limit.text

    # Platform Owner has no School-count restriction.
    second_school = await create_school(
        client, admin_headers, org["id"], name="AKSHARA SCHOOL", area="Pedana"
    )
    assert second_school["code"].startswith("AK-PDN-")

    # One client Organization correction per active Academic Year.
    first_correction = await client.patch(
        f"/api/v1/organizations/{org['id']}",
        headers={**org_admin_headers, "X-Change-Reason": "Correct Organization Head phone"},
        json={"head_phone": "9876543210"},
    )
    assert first_correction.status_code == 200, first_correction.text

    second_correction = await client.patch(
        f"/api/v1/organizations/{org['id']}",
        headers={**org_admin_headers, "X-Change-Reason": "Second client correction attempt"},
        json={"head_phone": "9876543211"},
    )
    assert second_correction.status_code == 409, second_correction.text
    assert "already been used" in second_correction.text

    # Super Admin is unlimited and can also change the allowed School count.
    super_override = await client.patch(
        f"/api/v1/organizations/{org['id']}",
        headers={
            **admin_headers,
            "X-Change-Reason": "Platform Owner approved additional School capacity",
        },
        json={"allowed_schools": 3, "head_phone": "9876543212"},
    )
    assert super_override.status_code == 200, super_override.text
    assert super_override.json()["allowed_schools"] == 3


@pytest.mark.asyncio
async def test_user_email_can_repeat_but_username_and_account_type_are_controlled(
    client: AsyncClient, admin_headers: dict[str, str]
):
    token = suffix()
    org = await create_org(
        client, admin_headers, name=f"User Group {token}", allowed_schools=1, token=token
    )
    school = await create_school(
        client, admin_headers, org["id"], name="AKSHARA SCHOOL", area="Razole"
    )
    org_admin_headers = await _login(
        client, f"orgadmin_{token.lower()}", TEST_PASSWORD, "ORGANIZATION_ADMIN"
    )

    shared_email = f"office.{token.lower()}@example.com"
    for account_type, username in (
        ("SCHOOL_ADMIN", f"school_{token.lower()}"),
        ("ACCOUNTS", f"accounts_{token.lower()}"),
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
            "organization_id": org["id"],
            "school_id": school["id"],
        },
    )
    assert duplicate_username.status_code == 409, duplicate_username.text

    mismatch_login = await client.post(
        "/api/v1/auth/login/json",
        json={
            "account_type": "TEACHER",
            "username": f"accounts_{token.lower()}",
            "password": TEST_PASSWORD,
        },
    )
    assert mismatch_login.status_code == 401
    assert "Invalid account type or login credentials" in mismatch_login.text


@pytest.mark.asyncio
async def test_super_admin_can_update_school_profile_with_udise_without_async_lazy_load(
    client: AsyncClient, admin_headers: dict[str, str]
):
    token = suffix()
    org = await create_org(
        client, admin_headers, name=f"Profile Group {token}", allowed_schools=1, token=token
    )
    udise = f"28{int(token, 16) % 100000000:08d}"
    school = await create_school(
        client,
        admin_headers,
        org["id"],
        name="AKSHARA SCHOOL",
        area="Razole",
        udise_codes=[{"udise_code": udise, "label": "Primary", "is_primary": True}],
    )

    response = await client.patch(
        f"/api/v1/schools/{school['id']}/profile",
        headers={**admin_headers, "X-Change-Reason": "Correct School profile information"},
        json={
            "configuration": {"tagline": "Educating for the future"},
            "udise_codes": [{"udise_code": udise, "label": "Primary", "is_primary": True}],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["configuration"]["tagline"] == "Educating for the future"
    assert body["udise_codes"][0]["udise_code"] == udise


@pytest.mark.asyncio
async def test_staff_username_login_and_uniqueness_are_case_insensitive(
    client: AsyncClient, admin_headers: dict[str, str]
):
    token = suffix()
    org = await create_org(
        client, admin_headers, name=f"Case Login {token}", allowed_schools=1, token=token
    )
    login = await client.post(
        "/api/v1/auth/login/json",
        json={
            "account_type": "ORGANIZATION_ADMIN",
            "username": f"ORGADMIN_{token}",
            "password": TEST_PASSWORD,
        },
    )
    assert login.status_code == 200, login.text

    school = await create_school(
        client, admin_headers, org["id"], name="AKSHARA SCHOOL", area="Razole"
    )
    first = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "username": f"Teacher_{token}",
            "password": TEST_PASSWORD,
            "full_name": "Case Teacher",
            "account_type": "TEACHER",
            "organization_id": org["id"],
            "school_id": school["id"],
        },
    )
    assert first.status_code == 201, first.text
    assert first.json()["username"] == f"teacher_{token.lower()}"

    duplicate = await client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "username": f"TEACHER_{token}",
            "password": TEST_PASSWORD,
            "full_name": "Duplicate Case Teacher",
            "account_type": "TEACHER",
            "organization_id": org["id"],
            "school_id": school["id"],
        },
    )
    assert duplicate.status_code == 409, duplicate.text


@pytest.mark.asyncio
async def test_password_reset_is_admin_only_and_hierarchy_is_enforced(
    client: AsyncClient, admin_headers: dict[str, str]
):
    token = suffix()
    org = await create_org(
        client, admin_headers, name=f"Reset Group {token}", allowed_schools=1, token=token
    )
    school = await create_school(
        client, admin_headers, org["id"], name="AKSHARA SCHOOL", area="Razole"
    )
    org_admin_headers = await _login(
        client, f"orgadmin_{token.lower()}", TEST_PASSWORD, "ORGANIZATION_ADMIN"
    )

    school_admin = await client.post(
        "/api/v1/users",
        headers=org_admin_headers,
        json={
            "username": f"schooladmin_{token}",
            "password": TEST_PASSWORD,
            "full_name": "School Admin",
            "designation": "Principal",
            "account_type": "SCHOOL_ADMIN",
            "organization_id": org["id"],
            "school_id": school["id"],
        },
    )
    assert school_admin.status_code == 201, school_admin.text
    teacher = await client.post(
        "/api/v1/users",
        headers=org_admin_headers,
        json={
            "username": f"teacher_{token}",
            "password": TEST_PASSWORD,
            "full_name": "Teacher User",
            "account_type": "TEACHER",
            "organization_id": org["id"],
            "school_id": school["id"],
        },
    )
    assert teacher.status_code == 201, teacher.text

    # Organization Admin may reset a lower-level School user.
    reset_teacher = await client.post(
        f"/api/v1/users/{teacher.json()['id']}/reset-password",
        headers=org_admin_headers,
        json={"new_password": "ResetTeacher@2026!"},
    )
    assert reset_teacher.status_code == 204, reset_teacher.text

    # Platform Owner may reset Organization Admin.
    org_users = await client.get(
        "/api/v1/users", headers=admin_headers, params={"organization_id": org["id"]}
    )
    org_admin = next(u for u in org_users.json() if u["account_type"] == "ORGANIZATION_ADMIN")

    # A school-scoped Platform Owner view includes the Organization Admin that
    # governs that school, while lower-level actors cannot opt into this view.
    platform_school_users = await client.get(
        "/api/v1/users",
        headers=admin_headers,
        params={"school_id": school["id"], "include_organization_admins": True},
    )
    assert platform_school_users.status_code == 200, platform_school_users.text
    assert org_admin["id"] in {user["id"] for user in platform_school_users.json()}

    denied_hierarchy_view = await client.get(
        "/api/v1/users",
        headers=org_admin_headers,
        params={"school_id": school["id"], "include_organization_admins": True},
    )
    assert denied_hierarchy_view.status_code == 403, denied_hierarchy_view.text

    reset_org_admin = await client.post(
        f"/api/v1/users/{org_admin['id']}/reset-password",
        headers=admin_headers,
        json={"new_password": "ResetOrgAdmin@2026!"},
    )
    assert reset_org_admin.status_code == 204, reset_org_admin.text

    # Functional users cannot obtain admin reset capability even if they know an ID.
    teacher_login = await client.post(
        "/api/v1/auth/login/json",
        json={
            "account_type": "TEACHER",
            "username": f"TEACHER_{token}",
            "password": "ResetTeacher@2026!",
        },
    )
    assert teacher_login.status_code == 200, teacher_login.text
    teacher_headers = {"Authorization": f"Bearer {teacher_login.json()['access_token']}"}
    denied = await client.post(
        f"/api/v1/users/{school_admin.json()['id']}/reset-password",
        headers=teacher_headers,
        json={"new_password": "ShouldNeverApply@2026!"},
    )
    # Temporary-password gate or RBAC may reject first; both preserve the invariant.
    assert denied.status_code == 403, denied.text
