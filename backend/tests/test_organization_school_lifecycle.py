import pytest
from httpx import AsyncClient

from tests.factories import create_org, create_school, suffix


@pytest.mark.asyncio
async def test_organization_disable_preserves_school_state_and_school_archive_preserves_data_identity(
    client: AsyncClient, admin_headers: dict[str, str]
):
    token = suffix()
    org = await create_org(
        client, admin_headers, name=f"AKSHARA SCHOOL {token}", allowed_schools=2, token=token
    )
    org_id = org["id"]
    assert org["code"].startswith("AK-ORG-")

    udise = f"28145{int(token[:6], 16) % 1000000:06d}"
    school = await create_school(
        client,
        admin_headers,
        org_id,
        name="AKSHARA SCHOOL",
        area="Razole",
        udise_codes=[{"udise_code": udise, "label": "Primary", "is_primary": True}],
    )
    school_id = school["id"]
    original_code = school["code"]

    disable_org = await client.patch(
        f"/api/v1/organizations/{org_id}/status",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert disable_org.status_code == 200, disable_org.text
    assert disable_org.json()["is_active"] is False

    # Organization disable is an access suspension only. Child School status and
    # every School data row remain untouched.
    schools = await client.get("/api/v1/schools", headers=admin_headers)
    row = next(item for item in schools.json() if item["id"] == school_id)
    assert row["is_active"] is True

    enable_org = await client.patch(
        f"/api/v1/organizations/{org_id}/status",
        headers=admin_headers,
        json={"is_active": True},
    )
    assert enable_org.status_code == 200, enable_org.text

    disable_school = await client.patch(
        f"/api/v1/schools/{school_id}/status",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert disable_school.status_code == 200, disable_school.text

    archived = await client.post(f"/api/v1/schools/{school_id}/archive", headers=admin_headers)
    assert archived.status_code == 200, archived.text
    assert archived.json()["deleted_at"] is not None
    assert archived.json()["code"] == original_code

    normal_list = await client.get("/api/v1/schools", headers=admin_headers)
    assert school_id not in {row["id"] for row in normal_list.json()}
    history_list = await client.get("/api/v1/schools?include_archived=true", headers=admin_headers)
    archived_row = next(row for row in history_list.json() if row["id"] == school_id)
    assert archived_row["deleted_at"] is not None

    # Same UDISE may be assigned to a replacement School after archive, but the
    # permanent ERP School code is never reused.
    recreated = await create_school(
        client,
        admin_headers,
        org_id,
        name="AKSHARA SCHOOL",
        area="Razole",
        udise_codes=[{"udise_code": udise, "label": "Primary", "is_primary": True}],
    )
    assert recreated["id"] != school_id
    assert recreated["code"] != original_code
    assert int(recreated["code"].rsplit("-", 1)[1]) > int(original_code.rsplit("-", 1)[1])

    restored = await client.post(f"/api/v1/schools/{school_id}/restore", headers=admin_headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["deleted_at"] is None
    assert restored.json()["is_active"] is False
    assert restored.json()["code"] == original_code


@pytest.mark.asyncio
async def test_platform_owner_can_archive_and_restore_disabled_organization_without_data_loss(
    client: AsyncClient, admin_headers: dict[str, str]
):
    token = suffix()
    org = await create_org(
        client, admin_headers, name=f"Archive Group {token}", allowed_schools=1, token=token
    )
    school = await create_school(
        client, admin_headers, org["id"], name="AKSHARA SCHOOL", area="Razole"
    )

    disabled = await client.patch(
        f"/api/v1/organizations/{org['id']}/status",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert disabled.status_code == 200, disabled.text

    archived = await client.post(
        f"/api/v1/organizations/{org['id']}/archive", headers=admin_headers
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["archived_at"] is not None
    assert archived.json()["is_active"] is False

    default_orgs = await client.get("/api/v1/organizations", headers=admin_headers)
    assert org["id"] not in {row["id"] for row in default_orgs.json()}
    with_archive = await client.get(
        "/api/v1/organizations?include_archived=true", headers=admin_headers
    )
    assert org["id"] in {row["id"] for row in with_archive.json()}

    # School records remain present; archive is Organization state, not data deletion.
    all_schools = await client.get("/api/v1/schools?include_archived=true", headers=admin_headers)
    assert school["id"] in {row["id"] for row in all_schools.json()}

    restored = await client.post(
        f"/api/v1/organizations/{org['id']}/restore", headers=admin_headers
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["archived_at"] is None
    assert restored.json()["is_active"] is False
