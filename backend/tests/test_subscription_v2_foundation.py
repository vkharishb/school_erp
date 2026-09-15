from pathlib import Path

from app.models.subscription import (
    OrganizationSubscription,
    SchoolSubscription,
    SubscriptionAgreementVersion,
    SubscriptionCommercialLedger,
)
from app.schemas.subscription import OrganizationSubscriptionCreate


def test_school_subscription_is_authoritative_plan_holder() -> None:
    assert "plan_id" in SchoolSubscription.__table__.columns
    assert "plan_snapshot" in SchoolSubscription.__table__.columns
    assert "base_student_capacity" in SchoolSubscription.__table__.columns
    assert "approved_extra_capacity" in SchoolSubscription.__table__.columns


def test_commercial_account_has_term_billing_identity_fields() -> None:
    assert "billing_mode" in OrganizationSubscription.__table__.columns
    assert "agreement_number" in OrganizationSubscription.__table__.columns
    assert "agreement_accepted_at" in OrganizationSubscription.__table__.columns
    assert OrganizationSubscriptionCreate.model_fields["billing_mode"].default == "organization"


def test_agreement_version_and_commercial_ledger_foundation_exist() -> None:
    assert SubscriptionAgreementVersion.__tablename__ == "subscription_agreement_versions"
    assert SubscriptionCommercialLedger.__tablename__ == "subscription_commercial_ledger"


def test_school_plan_lookup_uses_school_subscription_plan_id() -> None:
    source = (Path(__file__).resolve().parents[1] / "app" / "services" / "subscriptions.py").read_text(
        encoding="utf-8"
    )
    start = source.index("async def plan_for_school(")
    block = source[start : source.find("\n\n", start)]
    assert "SchoolSubscription.plan_id" in block or "entitlement.plan_id" in block


def test_no_downgrade_endpoint_is_exposed() -> None:
    api_root = Path(__file__).resolve().parents[1] / "app" / "api" / "v1"
    source = "\n".join(path.read_text(encoding="utf-8") for path in api_root.glob("*.py"))
    assert '@router.post("/downgrade' not in source
    assert '@subscriptions_router.post("/downgrade' not in source
