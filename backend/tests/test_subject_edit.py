import pytest
from httpx import AsyncClient

from tests.factories import create_org, create_school, main_campus_id, suffix


@pytest.mark.asyncio
async def test_admin_can_edit_subject_and_duplicate_code_is_blocked(
    client: AsyncClient, admin_headers: dict[str, str]
):
    token = suffix()
    org = await create_org(client, admin_headers, name=f"Subject Group {token}", token=token)
    school = await create_school(client, admin_headers, org["id"], name="Subject QA School")
    campus_id = await main_campus_id(client, admin_headers, school["id"])

    english = await client.post(
        f"/api/v1/students/campuses/{campus_id}/subjects",
        headers=admin_headers,
        json={"code": "ENG", "name": "English"},
    )
    assert english.status_code == 201, english.text

    maths = await client.post(
        f"/api/v1/students/campuses/{campus_id}/subjects",
        headers=admin_headers,
        json={"code": "MATH", "name": "Mathematics"},
    )
    assert maths.status_code == 201, maths.text

    updated = await client.patch(
        f"/api/v1/students/subjects/{english.json()['id']}",
        headers=admin_headers,
        json={"code": "ENG1", "name": "English Language"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["code"] == "ENG1"
    assert updated.json()["name"] == "English Language"

    duplicate = await client.patch(
        f"/api/v1/students/subjects/{english.json()['id']}",
        headers=admin_headers,
        json={"code": "math"},
    )
    assert duplicate.status_code == 409, duplicate.text
