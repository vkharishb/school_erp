import pytest
from httpx import AsyncClient

from tests.factories import create_org, create_org_year, create_school, suffix


@pytest.mark.asyncio
async def test_parent_student_shared_access_number_links_children_and_adds_yearly_charges_once(
    client: AsyncClient, admin_headers: dict[str, str]
):
    token = suffix()
    org = await create_org(
        client, admin_headers, name=f"ERP Access Group {token}", allowed_schools=1, token=token
    )
    school = await create_school(
        client, admin_headers, org["id"], name="AKSHARA SCHOOL", area="Razole"
    )
    org_year = await create_org_year(client, admin_headers, org["id"], activate=True)

    fee_head = await client.post(
        f"/api/v1/fees/{school['id']}/heads",
        headers=admin_headers,
        json={"code": "ERP-ACCESS", "name": "ERP Annual Access Fee", "is_misc": False},
    )
    assert fee_head.status_code == 201, fee_head.text

    policy = await client.put(
        f"/api/v1/erp-access/schools/{school['id']}/policy",
        headers=admin_headers,
        json={
            "organization_academic_year_id": org_year["id"],
            "fee_head_id": fee_head.json()["id"],
            "annual_amount": "600.00",
            "is_enabled": True,
        },
    )
    assert policy.status_code == 200, policy.text

    shared_phone = f"9{int(token[:7], 16) % 1000000000:09d}"
    guardian = await client.post(
        f"/api/v1/students/{school['id']}/guardians",
        headers=admin_headers,
        json={
            "name": "Parent One",
            "relationship_type": "Parent",
            "mobile": shared_phone,
            "is_primary": True,
        },
    )
    assert guardian.status_code == 201, guardian.text

    students = []
    for idx, first_name in enumerate(("Rahul", "Priya"), start=1):
        student = await client.post(
            f"/api/v1/students/{school['id']}",
            headers=admin_headers,
            json={
                "admission_number": f"ERP-{token}-{idx}",
                "first_name": first_name,
                "last_name": "Student",
                "guardian_ids": [guardian.json()["id"]],
            },
        )
        assert student.status_code == 201, student.text
        students.append(student.json())

    initial_password = "Parent@2026!Access"
    first_opt = await client.post(
        f"/api/v1/erp-access/schools/{school['id']}/opt-in",
        headers=admin_headers,
        json={
            "student_id": students[0]["id"],
            "access_number": shared_phone,
            "initial_password": initial_password,
        },
    )
    assert first_opt.status_code == 201, first_opt.text
    assert first_opt.json()["status"] == "ACTIVE"
    assert first_opt.json()["login_account_created"] is True
    assert first_opt.json()["charge_id"]

    second_opt = await client.post(
        f"/api/v1/erp-access/schools/{school['id']}/opt-in",
        headers=admin_headers,
        json={
            "student_id": students[1]["id"],
            "access_number": shared_phone,
        },
    )
    assert second_opt.status_code == 201, second_opt.text
    assert second_opt.json()["login_account_created"] is False

    # Repeated opt-in must not duplicate annual access or annual ledger charge.
    duplicate_opt = await client.post(
        f"/api/v1/erp-access/schools/{school['id']}/opt-in",
        headers=admin_headers,
        json={"student_id": students[0]["id"], "access_number": shared_phone},
    )
    assert duplicate_opt.status_code == 409, duplicate_opt.text

    for student in students:
        charges = await client.get(
            f"/api/v1/fees/{school['id']}/students/{student['id']}/charges",
            headers=admin_headers,
        )
        assert charges.status_code == 200, charges.text
        erp_charges = [row for row in charges.json() if row["fee_head_id"] == fee_head.json()["id"]]
        assert len(erp_charges) == 1
        assert erp_charges[0]["amount"] == "600.00"

    login = await client.post(
        "/api/v1/auth/login/json",
        json={
            "account_type": "PARENT_STUDENT",
            "username": shared_phone,
            "password": initial_password,
        },
    )
    assert login.status_code == 200, login.text
    parent_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # School-issued temporary credentials must be changed before portal access.
    blocked = await client.get("/api/v1/parent-student/me/students", headers=parent_headers)
    assert blocked.status_code == 403, blocked.text
    changed_password = "ParentChanged@2026!Access"
    changed = await client.post(
        "/api/v1/auth/change-password",
        headers=parent_headers,
        json={"current_password": initial_password, "new_password": changed_password},
    )
    assert changed.status_code == 204, changed.text
    relogin = await client.post(
        "/api/v1/auth/login/json",
        json={
            "account_type": "PARENT_STUDENT",
            "username": shared_phone,
            "password": changed_password,
        },
    )
    assert relogin.status_code == 200, relogin.text
    parent_headers = {"Authorization": f"Bearer {relogin.json()['access_token']}"}

    linked = await client.get("/api/v1/parent-student/me/students", headers=parent_headers)
    assert linked.status_code == 200, linked.text
    assert {row["id"] for row in linked.json()} == {student["id"] for student in students}

    summary = await client.get(
        f"/api/v1/parent-student/students/{students[0]['id']}/summary",
        headers=parent_headers,
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["student"]["id"] == students[0]["id"]
    assert summary.json()["fees"]["total"] == "600.00"
