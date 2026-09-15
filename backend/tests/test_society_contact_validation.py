from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import SubscriptionPlan


@pytest.mark.asyncio
async def test_society_creation_rejects_invalid_email_with_shared_message(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
):
    token = uuid4().hex[:8]

    trial = (
        await db_session.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.code == "TRIAL")
        )
    ).scalar_one()

    response = await client.post(
        "/api/v1/organizations",
        headers=admin_headers,
        json={
            "name": f"Invalid Email Society {token}",
            "allowed_schools": 2,
            "head_full_name": "Validation Administrator",
            "head_email": "invalid-email",
            "head_phone": "9876543210",
            "admin_username": f"validation_{token}",
            "admin_designation": "Administrator",
            "admin_email": "invalid-email",
            "subscription_plan_id": str(trial.id),
            "billing_cycle": "trial",
            "discount_type": "none",
            "discount_value": "0",
            "tax_mode": "non_gst",
            "tax_rate": "0",
        },
    )

    assert response.status_code == 422

    body = response.json()
    messages = [
      str(error.get("message", ""))
      for error in body.get("error", {}).get("details", [])
      if isinstance(error, dict)
    ]

    messages.append(str(body.get("error", {}).get("message", "")))

    assert any(
        "Please enter a valid email address." in message
        for message in messages
    ), body
