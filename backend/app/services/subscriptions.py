import hashlib
from calendar import monthrange
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.license import SchoolLicense
from app.models.subscription import (OrganizationSubscription, SchoolSubscription, SubscriptionPlan,
    SubscriptionAgreementVersion, SubscriptionCommercialLedger)
from app.services.licensing import IMPLEMENTED_MODULES

MONEY = Decimal("0.01")
TRIAL_MODULES = {"dashboard", "school_admin", "school_config", "student", "teacher", "fee"}


def money(value: Decimal | int | str | None) -> Decimal:
    return Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)


def add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def expiry_for(start: datetime, cycle: str, trial_days: int = 30) -> datetime:
    if cycle == "trial":
        return start + timedelta(days=trial_days)
    if cycle == "monthly":
        return add_months(start, 1)
    # Paid yearly subscriptions align to the ERP commercial/academic year ending 31 May.
    end_year = start.year if start.month <= 5 else start.year + 1
    return start.replace(year=end_year, month=5, day=31, hour=23, minute=59, second=59, microsecond=0)


def grace_until_for(expires_at: datetime, cycle: str) -> datetime | None:
    # Trial is fixed and cannot be renewed/restarted. Paid plans receive 30 days.
    return None if cycle == "trial" else expires_at + timedelta(days=30)


def activation_hash(code: str) -> str:
    return hashlib.sha256(
        f"{get_settings().secret_key}:{code.strip().upper()}".encode()
    ).hexdigest()


def activation_mask(last4: str) -> str:
    return f"SERP-ACT-****-****-{last4}"


def effective_modules(plan: SubscriptionPlan, *, trial: bool) -> list[str]:
    # Paid plans use exactly the Platform Owner catalog mapping; trial is fixed/restricted.
    requested = TRIAL_MODULES if trial else set(plan.enabled_modules or [])
    return sorted(requested & set(IMPLEMENTED_MODULES))


def calculate_financials(
    list_amount: Decimal,
    discount_type: str,
    discount_value: Decimal,
    tax_mode: str,
    tax_rate: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    price = money(list_amount)
    value = money(discount_value)
    if discount_type == "percent":
        if value > 100:
            raise ValueError("Percentage discount cannot exceed 100")
        discount = money(price * value / Decimal("100"))
    elif discount_type == "fixed":
        discount = value
    else:
        discount = Decimal("0.00")
    if discount > price:
        raise ValueError("Discount cannot exceed the plan amount")
    taxable = price - discount
    tax = money(taxable * money(tax_rate) / Decimal("100")) if tax_mode == "gst" else Decimal("0.00")
    return discount, tax, money(taxable + tax)


async def create_organization_subscription(
    db: AsyncSession,
    *,
    organization_id: UUID,
    plan: SubscriptionPlan,
    billing_cycle: str,
    school_count: int,
    billing_mode: str = "organization",
    discount_type: str = "none",
    discount_value: Decimal = Decimal("0"),
    discount_reason: str | None = None,
    tax_mode: str = "non_gst",
    tax_rate: Decimal = Decimal("0"),
    activation_minimum_amount: Decimal | None = None,
    customized_total_amount: Decimal | None = None,
    activation_override_reason: str | None = None,
    activation_overridden_by: UUID | None = None,
    starts_at: datetime | None = None,
    due_at: datetime | None = None,
    notes: str | None = None,
    created_by: UUID | None = None,
) -> OrganizationSubscription:
    start = starts_at or datetime.now(UTC)
    code = plan.code.upper()
    if code == "TRIAL":
        billing_cycle = "trial"
        if school_count != 1:
            raise ValueError("Trial plan allows only 1 School per Society/Trust")
    elif code in {"BASIC", "STANDARD", "PREMIUM"} and billing_cycle != "yearly":
        raise ValueError(f"{plan.name} is a yearly-only plan")
    elif code in {"CUSTOMIZED", "PAYG"} and billing_cycle not in {"monthly", "yearly"}:
        raise ValueError(f"{plan.name} supports monthly or yearly billing only")

    if billing_cycle == "trial":
        if not plan.is_trial_available:
            raise ValueError("Trial is not available for this plan")
        list_amount = Decimal("0")
        discount_type = "none"
        discount_value = Decimal("0")
        discount_reason = None
        tax_mode = "non_gst"
        tax_rate = Decimal("0")
        activation_minimum_amount = None
        activation_override_reason = None
        due_at = None
    else:
        if due_at is None:
            raise ValueError("Payment Due Date is required for paid plans")
        if tax_mode == "non_gst":
            tax_rate = Decimal("0")

        if code == "CUSTOMIZED":
            if customized_total_amount is None or customized_total_amount <= 0:
                raise ValueError("Customized Total Amount must be greater than zero")
            list_amount = money(customized_total_amount)
        else:
            if customized_total_amount is not None:
                raise ValueError("Customized Total Amount is only allowed for Customized plans")
            unit_price = plan.monthly_price if billing_cycle == "monthly" else plan.yearly_price
            if code == "PAYG":
                # PAYG is Premium module entitlement priced per student. The configured
                # monthly/yearly rate is multiplied by the contractual student basis per School.
                list_amount = money(unit_price * max(plan.minimum_students, 1) * school_count)
            else:
                list_amount = money(unit_price * school_count)
    discount, tax, finalized = calculate_financials(
        list_amount, discount_type, discount_value, tax_mode, tax_rate
    )
    calculated_minimum = Decimal("0.00") if billing_cycle == "trial" else money(finalized * Decimal("0.50"))
    minimum = money(activation_minimum_amount) if billing_cycle != "trial" and activation_minimum_amount is not None else calculated_minimum
    override_used = billing_cycle != "trial" and minimum < calculated_minimum
    if override_used and not (activation_override_reason or "").strip():
        raise ValueError("Reason is required when Minimum Activation Payment is below the calculated minimum")
    if minimum > finalized:
        raise ValueError("Activation minimum cannot exceed the finalized amount")
    row = OrganizationSubscription(
        organization_id=organization_id, plan_id=plan.id, billing_mode=billing_mode, billing_cycle=billing_cycle,
        school_count=school_count, list_amount=money(list_amount), discount_type=discount_type,
        discount_value=money(discount_value), discount_amount=discount,
        discount_reason=discount_reason, tax_mode=tax_mode, tax_rate=money(tax_rate),
        tax_amount=tax, finalized_amount=finalized, total_received=Decimal("0.00"),
        balance_amount=finalized, activation_minimum_amount=minimum,
        activation_minimum_original=calculated_minimum, activation_override_used=override_used,
        activation_override_reason=(activation_override_reason.strip() if override_used else None),
        activation_overridden_by=(activation_overridden_by if override_used else None),
        activation_overridden_at=(start if override_used else None),
        payment_status="not_required" if billing_cycle == "trial" else "unpaid",
        status="trial" if billing_cycle == "trial" else "pending_payment",
        starts_at=start, expires_at=expiry_for(start, billing_cycle, 30),
        grace_until=grace_until_for(expiry_for(start, billing_cycle, 30), billing_cycle),
        due_at=due_at, notes=notes, created_by=created_by,
    )
    db.add(row)
    await db.flush()
    snapshot = {
        "legacy_default_plan_id": str(plan.id), "billing_cycle": billing_cycle,
        "billing_mode": billing_mode, "school_count": school_count,
        "list_amount": str(row.list_amount), "discount_type": discount_type,
        "discount_value": str(row.discount_value), "tax_mode": tax_mode,
        "tax_rate": str(row.tax_rate), "finalized_amount": str(row.finalized_amount),
        "activation_minimum_amount": str(row.activation_minimum_amount),
    }
    db.add(SubscriptionAgreementVersion(
        organization_subscription_id=row.id, version_no=1, change_type="initial",
        snapshot=snapshot, effective_at=start, created_by=created_by,
    ))
    db.add(SubscriptionCommercialLedger(
        organization_subscription_id=row.id, entry_type="opening_agreement",
        amount=row.finalized_amount, metadata_json={"source": "V1.1.24.01"},
        effective_at=start, created_by=created_by,
    ))
    await db.flush()
    return row


async def attach_school_entitlement(
    db: AsyncSession,
    *,
    account: OrganizationSubscription,
    plan: SubscriptionPlan,
    school_id: UUID,
    created_by: UUID | None,
) -> tuple[SchoolSubscription, SchoolLicense]:
    count = int((await db.execute(select(func.count(SchoolSubscription.id)).where(
        SchoolSubscription.organization_subscription_id == account.id
    ))).scalar_one() or 0)
    if count >= account.school_count:
        raise ValueError(f"Organization subscription permits {account.school_count} schools")
    trial = account.billing_cycle == "trial"
    access_until = account.expires_at if trial else (account.grace_until or account.expires_at)
    snapshot = {
        "plan_id": str(plan.id), "code": plan.code, "name": plan.name,
        "student_limit": plan.student_limit, "teacher_limit": plan.teacher_limit,
        "enabled_modules": list(plan.enabled_modules or []),
        "monthly_price": str(plan.monthly_price), "yearly_price": str(plan.yearly_price),
    }
    entitlement = SchoolSubscription(
        school_id=school_id, organization_subscription_id=account.id, plan_id=plan.id,
        plan_snapshot=snapshot, billing_cycle=account.billing_cycle,
        base_student_capacity=plan.student_limit, approved_extra_capacity=0,
        status="trial" if trial else "pending_activation",
        starts_at=account.starts_at, expires_at=access_until, created_by=created_by,
    )
    db.add(entitlement)
    license_ = SchoolLicense(
        school_id=school_id, license_key=f"SUBSCRIPTION-{school_id}",
        enabled_modules=effective_modules(plan, trial=trial),
        max_users=min(plan.max_users, 10) if trial else plan.max_users,
        starts_at=account.starts_at, expires_at=access_until,
        # Trial is immediately usable. Paid Schools remain operationally locked
        # until the Organization Admin completes ERP activation after the
        # commercial minimum-payment and activation-key checks.
        is_active=trial,
    )
    db.add(license_)
    await db.flush()
    return entitlement, license_


def refresh_payment_status(account: OrganizationSubscription) -> None:
    now = datetime.now(UTC)
    if account.billing_cycle == "trial":
        account.payment_status = "not_required"
        account.status = "expired" if account.expires_at < now else "trial"
    elif account.balance_amount <= 0:
        account.payment_status = "paid"
        account.status = "active"
    elif account.due_at and account.due_at < now:
        account.payment_status = "overdue"
        account.status = "overdue"
    elif account.total_received > 0:
        account.payment_status = "partially_paid"
        account.status = "active" if account.total_received >= account.activation_minimum_amount else "pending_payment"
    else:
        account.payment_status = "unpaid"
        account.status = "pending_payment"

async def plan_for_school(db: AsyncSession, school_id: UUID) -> SubscriptionPlan | None:
    """Return the plan currently governing a School entitlement."""
    entitlement = (await db.execute(
        select(SchoolSubscription)
        .where(SchoolSubscription.school_id == school_id)
        .order_by(SchoolSubscription.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if not entitlement:
        return None
    return await db.get(SubscriptionPlan, entitlement.plan_id)

async def require_trial_capability(db: AsyncSession, school_id: UUID, capability: str) -> SubscriptionPlan | None:
    plan = await plan_for_school(db, school_id)
    if not plan or plan.code.upper() != "TRIAL":
        return plan
    blocked = {"student.edit", "teacher.edit", "reports", "receipts", "exports", "bulk_upload"}
    if capability in blocked:
        raise ValueError(f"{capability.replace('_',' ').replace('.',' ')} is disabled in the 30-Day Trial")
    return plan

