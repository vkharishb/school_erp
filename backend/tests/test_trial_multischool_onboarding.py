from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import OrganizationSubscription, SubscriptionPlan


@pytest.mark.asyncio
async def test_trial_organization_is_forced_to_single_school_capacity(
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
            "name": f"Multi School Trial Society {token}",
            "allowed_schools": 5,
            "head_full_name": "Trial Administrator",
            "head_email": f"trial.{token}@example.com",
            "head_phone": "9876543210",
            "admin_username": f"trial_admin_{token}",
            "admin_designation": "Administrator",
            "admin_email": f"trial.{token}@example.com",
            "subscription_plan_id": str(trial.id),
            "billing_cycle": "trial",
            "discount_type": "none",
            "discount_value": "0",
            "tax_mode": "non_gst",
            "tax_rate": "0",
        },
    )

    assert response.status_code == 201, response.text

    organization = response.json()
    assert organization["allowed_schools"] == 1
    assert organization["head_phone"] == "+919876543210"

    subscription = (
        await db_session.execute(
            select(OrganizationSubscription).where(
                OrganizationSubscription.organization_id == organization["id"]
            )
        )
    ).scalar_one()

    assert subscription.plan_id == trial.id
    assert subscription.school_count == 1
    assert subscription.billing_cycle == "trial"

    assert subscription.list_amount == Decimal("0.00")
    assert subscription.discount_amount == Decimal("0.00")
    assert subscription.tax_amount == Decimal("0.00")
    assert subscription.finalized_amount == Decimal("0.00")
    assert subscription.balance_amount == Decimal("0.00")

    assert subscription.activation_minimum_amount == Decimal("0.00")
    assert subscription.activation_minimum_original == Decimal("0.00")
    assert subscription.activation_override_used is False

    assert subscription.payment_status == "not_required"
    assert subscription.status == "trial"
    assert subscription.due_at is None

    assert subscription.expires_at - subscription.starts_at == timedelta(days=30)
