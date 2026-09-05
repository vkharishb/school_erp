import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_mutation_requires_confirmation_and_reason_before_endpoint_execution():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as raw:
        not_confirmed = await raw.post("/api/v1/organizations", json={})
        assert not_confirmed.status_code == 428
        assert not_confirmed.json()["error"]["code"] == "change_confirmation_required"

        missing_reason = await raw.post(
            "/api/v1/organizations",
            headers={"X-Change-Confirmed": "true"},
            json={},
        )
        assert missing_reason.status_code == 422
        assert missing_reason.json()["error"]["code"] == "change_reason_required"
