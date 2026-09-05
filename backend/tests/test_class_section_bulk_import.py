from pathlib import Path

import pytest
from httpx import AsyncClient

from tests.factories import create_org, create_school, main_campus_id, suffix

FIXTURE = Path(__file__).parent / "fixtures" / "classes-sections-import-sample.xlsx"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.mark.asyncio
async def test_merged_class_section_import_creates_classes_and_sections(
    client: AsyncClient, admin_headers: dict[str, str]
):
    token = suffix()
    org = await create_org(
        client, admin_headers, name=f"Bulk Structure {token}", allowed_schools=1, token=token
    )
    school = await create_school(
        client, admin_headers, org["id"], name="AKSHARA SCHOOL", area="Razole"
    )
    campus_id = await main_campus_id(client, admin_headers, school["id"])
    workbook = FIXTURE.read_bytes()

    preview = await client.post(
        f"/api/v1/imports/classes-sections/{school['id']}/preview",
        headers=admin_headers,
        data={"campus_id": campus_id},
        files={"file": ("classes-sections-import.xlsx", workbook, XLSX)},
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["row_count"] == 2
    assert body["error_count"] == 0
    assert body["summary"]["new_classes"] == 2
    assert body["summary"]["new_sections"] == 5

    confirmed = await client.post(
        f"/api/v1/imports/classes-sections/{school['id']}/confirm",
        headers=admin_headers,
        data={"campus_id": campus_id, "expected_sha256": body["sha256"]},
        files={"file": ("classes-sections-import.xlsx", workbook, XLSX)},
    )
    assert confirmed.status_code == 200, confirmed.text
    result = confirmed.json()
    assert result["classes_created"] == 2
    assert result["sections_created"] == 5
    assert result["imported"] == 7

    classes = await client.get(
        f"/api/v1/students/campuses/{campus_id}/classes", headers=admin_headers
    )
    assert classes.status_code == 200, classes.text
    by_name = {row["name"]: row for row in classes.json()}
    assert {"Class 1", "Class 2"}.issubset(by_name)

    class_1_sections = await client.get(
        f"/api/v1/students/classes/{by_name['Class 1']['id']}/sections", headers=admin_headers
    )
    assert class_1_sections.status_code == 200, class_1_sections.text
    assert {row["name"] for row in class_1_sections.json()} == {"A", "B"}

    class_2_sections = await client.get(
        f"/api/v1/students/classes/{by_name['Class 2']['id']}/sections", headers=admin_headers
    )
    assert class_2_sections.status_code == 200, class_2_sections.text
    assert {row["name"] for row in class_2_sections.json()} == {"A", "B", "C"}


@pytest.mark.asyncio
async def test_merged_class_section_import_reuses_existing_records(
    client: AsyncClient, admin_headers: dict[str, str]
):
    token = suffix()
    org = await create_org(
        client, admin_headers, name=f"Bulk Reuse {token}", allowed_schools=1, token=token
    )
    school = await create_school(
        client, admin_headers, org["id"], name="AKSHARA SCHOOL", area="Razole"
    )
    campus_id = await main_campus_id(client, admin_headers, school["id"])
    workbook = FIXTURE.read_bytes()

    preview = await client.post(
        f"/api/v1/imports/classes-sections/{school['id']}/preview",
        headers=admin_headers,
        data={"campus_id": campus_id},
        files={"file": ("classes-sections-import.xlsx", workbook, XLSX)},
    )
    first = preview.json()
    confirmed = await client.post(
        f"/api/v1/imports/classes-sections/{school['id']}/confirm",
        headers=admin_headers,
        data={"campus_id": campus_id, "expected_sha256": first["sha256"]},
        files={"file": ("classes-sections-import.xlsx", workbook, XLSX)},
    )
    assert confirmed.status_code == 200, confirmed.text

    second_preview = await client.post(
        f"/api/v1/imports/classes-sections/{school['id']}/preview",
        headers=admin_headers,
        data={"campus_id": campus_id},
        files={"file": ("classes-sections-import.xlsx", workbook, XLSX)},
    )
    assert second_preview.status_code == 200, second_preview.text
    body = second_preview.json()
    assert body["error_count"] == 0
    assert body["summary"]["new_classes"] == 0
    assert body["summary"]["new_sections"] == 0
    assert body["summary"]["existing_classes"] == 2
    assert body["summary"]["existing_sections"] == 5
