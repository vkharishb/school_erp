import pytest
from httpx import AsyncClient

from tests.factories import create_org, create_school, main_campus_id, suffix


@pytest.mark.asyncio
async def test_student_identity_and_organization_academic_year_enrollment_policy(
    client: AsyncClient, admin_headers: dict[str, str]
):
    token = suffix()
    org = await create_org(
        client, admin_headers, name=f"Student Group {token}", allowed_schools=1, token=token
    )
    school = await create_school(
        client,
        admin_headers,
        org["id"],
        name="AKSHARA SCHOOL",
        area="Razole",
    )
    school_id = school["id"]
    campus_id = await main_campus_id(client, admin_headers, school_id)

    year_26 = await client.post(
        f"/api/v1/organizations/{org['id']}/academic-years",
        headers=admin_headers,
        json={
            "code": "2026-27",
            "name": "Academic Year 2026-27",
            "starts_on": "2026-06-01",
            "ends_on": "2027-05-31",
        },
    )
    assert year_26.status_code == 201, year_26.text
    activate_26 = await client.post(
        f"/api/v1/organizations/academic-years/{year_26.json()['id']}/activate",
        headers=admin_headers,
    )
    assert activate_26.status_code == 200, activate_26.text

    year_27 = await client.post(
        f"/api/v1/organizations/{org['id']}/academic-years",
        headers=admin_headers,
        json={
            "code": "2027-28",
            "name": "Academic Year 2027-28",
            "starts_on": "2027-06-01",
            "ends_on": "2028-05-31",
        },
    )
    assert year_27.status_code == 201, year_27.text
    activate_27 = await client.post(
        f"/api/v1/organizations/academic-years/{year_27.json()['id']}/activate",
        headers=admin_headers,
    )
    assert activate_27.status_code == 200, activate_27.text

    campus_years = await client.get(
        f"/api/v1/foundation/campuses/{campus_id}/academic-years",
        headers=admin_headers,
    )
    by_code = {row["code"]: row for row in campus_years.json()}
    year_26_id = by_code["2026-27"]["id"]
    year_27_id = by_code["2027-28"]["id"]
    assert by_code["2026-27"]["status"] == "closed"
    assert by_code["2027-28"]["status"] == "active"

    academic_class = await client.post(
        f"/api/v1/students/campuses/{campus_id}/classes",
        headers=admin_headers,
        json={"code": f"TEST10-{token}", "name": "Test Class 10", "sort_order": 10},
    )
    assert academic_class.status_code == 201, academic_class.text
    class_id = academic_class.json()["id"]

    section = await client.post(
        f"/api/v1/students/classes/{class_id}/sections",
        headers=admin_headers,
        json={"code": "A", "name": "Section A"},
    )
    assert section.status_code == 201, section.text
    section_id = section.json()["id"]

    student = await client.post(
        f"/api/v1/students/{school_id}",
        headers=admin_headers,
        json={
            "admission_number": f"TEST-{token}",
            "first_name": "Test",
            "last_name": "Student",
            "gender": "other",
            "date_of_birth": "2015-06-15",
        },
    )
    assert student.status_code == 201, student.text
    student_data = student.json()
    student_id = student_data["id"]
    assert student_data["admission_number"] == f"TEST-{token}"
    assert student_data["student_code"].startswith("STU-")
    assert student_data["campus_id"] == campus_id

    enrollment_payload = {
        "academic_year_id": year_26_id,
        "academic_class_id": class_id,
        "section_id": section_id,
        "enrolled_on": "2026-06-01",
    }
    historical = await client.post(
        f"/api/v1/students/{student_id}/enrollments",
        headers=admin_headers,
        json=enrollment_payload,
    )
    assert historical.status_code == 409
    assert "Historical academic year is read-only" in historical.text

    enrollment_payload["academic_year_id"] = year_27_id
    enrollment_payload["enrolled_on"] = "2027-06-01"
    active = await client.post(
        f"/api/v1/students/{student_id}/enrollments",
        headers=admin_headers,
        json=enrollment_payload,
    )
    assert active.status_code == 201, active.text
    assert active.json()["student_id"] == student_id
    assert active.json()["academic_year_id"] == year_27_id
    assert active.json()["status"] == "active"

    duplicate = await client.post(
        f"/api/v1/students/{student_id}/enrollments",
        headers=admin_headers,
        json=enrollment_payload,
    )
    assert duplicate.status_code == 409
