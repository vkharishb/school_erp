import pytest
from httpx import AsyncClient

from app.services.licensing import (
    CORE_MODULES,
    IMPLEMENTED_MODULES,
    PHASE1_MODULES,
    require_core_modules,
)
from tests.factories import create_org, create_school


def test_school_config_is_a_phase1_implemented_module():
    assert "school_config" in PHASE1_MODULES
    assert "school_config" in IMPLEMENTED_MODULES


def test_every_phase1_module_is_mandatory_core():
    assert CORE_MODULES == set(PHASE1_MODULES)
    require_core_modules(PHASE1_MODULES)
    with pytest.raises(ValueError, match="Mandatory core modules cannot be disabled"):
        require_core_modules([module for module in PHASE1_MODULES if module != "fee"])


@pytest.mark.asyncio
async def test_platform_cannot_disable_phase1_core_in_organization_or_school_license(
    client: AsyncClient,
    admin_headers: dict[str, str],
):
    organization = await create_org(client, admin_headers)
    school = await create_school(client, admin_headers, organization["id"])
    incomplete = [module for module in PHASE1_MODULES if module != "attendance"]

    organization_update = await client.patch(
        f"/api/v1/organizations/{organization['id']}/license",
        headers=admin_headers,
        json={"enabled_modules": incomplete},
    )
    assert organization_update.status_code == 422, organization_update.text
    assert "mandatory core modules cannot be disabled" in organization_update.text.lower()

    school_update = await client.patch(
        f"/api/v1/schools/{school['id']}/license",
        headers=admin_headers,
        json={"enabled_modules": incomplete},
    )
    assert school_update.status_code == 422, school_update.text
    assert "mandatory core modules cannot be disabled" in school_update.text.lower()
