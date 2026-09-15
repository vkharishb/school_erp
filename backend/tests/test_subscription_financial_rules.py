from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.subscription import SubscriptionPlan
from app.services.subscriptions import add_months, calculate_financials, effective_modules, expiry_for, money


def test_organization_financials_apply_discount_then_gst() -> None:
    discount, tax, finalized = calculate_financials(
        Decimal("50000"), "percent", Decimal("10"), "gst", Decimal("18")
    )
    assert discount == Decimal("5000.00")
    assert tax == Decimal("8100.00")
    assert finalized == Decimal("53100.00")
    assert money(finalized * Decimal("0.50")) == Decimal("26550.00")


def test_discount_cannot_exceed_organization_price() -> None:
    with pytest.raises(ValueError, match="Discount cannot exceed"):
        calculate_financials(Decimal("1000"), "fixed", Decimal("1001"), "non_gst", 0)


def test_trial_is_exactly_thirty_days_and_monthly_yearly_preserve_day() -> None:
    start = datetime(2026, 1, 31, 10, tzinfo=UTC)
    assert expiry_for(start, "trial", 30) - start == timedelta(days=30)
    assert add_months(start, 1).date().isoformat() == "2026-02-28"
    assert add_months(start, 12).date().isoformat() == "2027-01-31"


def test_trial_has_restricted_modules_while_paid_plan_retains_core() -> None:
    plan = SubscriptionPlan(
        code="QA", name="QA", enabled_modules=["dashboard", "student", "fee", "marks", "reports", "communication"]
    )
    trial = set(effective_modules(plan, trial=True))
    # DEV.17+ policy: Trial exposes Student, Teacher and Fee modules, while
    # action-level trial policy restricts edit/export/report/receipt/bulk workflows.
    assert {"dashboard", "student", "teacher", "fee"}.issubset(trial)
    assert {"marks", "reports"}.isdisjoint(trial)

    # Paid plans use the exact Platform Owner catalog mapping; they are no longer
    # expanded to every Phase-1 core module automatically.
    paid = set(effective_modules(plan, trial=False))
    assert {"dashboard", "student", "fee", "marks", "reports"}.issubset(paid)
    assert "teacher" not in paid
    assert "communication" not in paid
