import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_non_delete_mutation_does_not_require_generic_change_confirmation():
    """
    Non-Delete mutations must not be intercepted by the legacy generic
    X-Change-Confirmed / X-Change-Reason policy.

    An unauthenticated mutation should therefore reach the normal
    authentication layer and return 401 rather than the legacy 428/422
    change-control responses.
    """
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as raw:
        response = await raw.post(
            "/api/v1/organizations",
            json={},
        )

        assert response.status_code == 401, response.text

        error = response.json()["error"]

        assert error["code"] not in {
            "change_confirmation_required",
            "change_reason_required",
        }


@pytest.mark.asyncio
async def test_legacy_change_headers_are_not_required_for_non_delete_mutations():
    """
    Legacy confirmation headers must not control ordinary Create/Update
    operations.

    Supplying the old headers to an unauthenticated request must not cause
    the legacy change-control middleware to return its former 428/422
    responses. Authentication remains the applicable security boundary.
    """
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as raw:
        response = await raw.post(
            "/api/v1/organizations",
            headers={
                "X-Change-Confirmed": "true",
                "X-Change-Reason": "Legacy QA header",
            },
            json={},
        )

        assert response.status_code == 401, response.text

        error = response.json()["error"]

        assert error["code"] not in {
            "change_confirmation_required",
            "change_reason_required",
        }