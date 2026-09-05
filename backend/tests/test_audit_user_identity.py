import pytest
from httpx import AsyncClient

from app.core.config import get_settings


@pytest.mark.asyncio
async def test_audit_events_expose_actor_name_and_username(
    client: AsyncClient,
    admin_headers: dict[str, str],
):
    response = await client.get("/api/v1/audit", headers=admin_headers)
    assert response.status_code == 200, response.text

    rows = [row for row in response.json() if row.get("username") == "superadmin"]
    assert rows, response.text
    assert rows[0]["user_name"] == get_settings().super_admin_full_name
    assert rows[0]["user_id"]
    assert rows[0]["metadata"]["actor_name"] == get_settings().super_admin_full_name
    assert rows[0]["metadata"]["actor_username"] == "superadmin"
