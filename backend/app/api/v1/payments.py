import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_superuser, get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.license import SchoolLicense
from app.models.organization import Organization
from app.models.school import School, SchoolConfiguration
from app.models.subscription import (
    OrganizationSubscription, SchoolSubscription, SubscriptionActivationKey,
    SubscriptionBillingSettings, SubscriptionPayment, SubscriptionPaymentReminder,
    SubscriptionPlan,
)
from app.models.user import User
from app.schemas.subscription import (
    ActivationKeyGenerate, ActivationKeyGeneratedOut, ActivationKeyOut, ActivationRequest,
    ActivationResult, ActivationRevoke, ActivationTermsOut, OrganizationActivationSchoolOut,
    OrganizationSubscriptionCreate, OrganizationSubscriptionOut, OrganizationSubscriptionUpdate,
    PaymentReceiptOut, PlatformPaymentSummary, ReminderCreate, ReminderOut,
    SchoolSubscriptionDisable, SchoolSubscriptionOut, SubscriptionBillingSettingsOut, SubscriptionBillingSettingsUpdate,
    SubscriptionPaymentCreate, SubscriptionPaymentOut, SubscriptionPlanCreate,
    SubscriptionPlanOut, SubscriptionPlanUpdate, SubscriptionStatementOut, TrialConversion,
    SubscriptionRenewalRequest, SubscriptionExtensionRequest,
)
from app.services.audit import record_audit
from app.services.session_control import revoke_school_sessions
from app.services.subscriptions import (
    activation_hash, activation_mask, calculate_financials,
    create_organization_subscription, effective_modules, expiry_for, grace_until_for, money, refresh_payment_status,
)

payments_router = APIRouter(prefix="/payments", tags=["Platform Payments"])
subscriptions_router = APIRouter(prefix="/subscriptions", tags=["Platform Subscriptions"])


async def _settings(db: AsyncSession) -> SubscriptionBillingSettings:
    row = await db.get(SubscriptionBillingSettings, 1)
    if row is None:
        row = SubscriptionBillingSettings(id=1)
        db.add(row)
        await db.flush()
    return row


async def _org_account_out(db: AsyncSession, row: OrganizationSubscription) -> OrganizationSubscriptionOut:
    organization = await db.get(Organization, row.organization_id)
    plan = await db.get(SubscriptionPlan, row.plan_id)
    count = int((await db.execute(select(func.count(SchoolSubscription.id)).where(
        SchoolSubscription.organization_subscription_id == row.id
    ))).scalar_one() or 0)
    refresh_payment_status(row)
    return OrganizationSubscriptionOut(
        id=row.id, organization_id=row.organization_id,
        organization_name=organization.name if organization else "Unavailable organization",
        organization_code=organization.code if organization else "—",
        plan_id=row.plan_id, billing_mode=row.billing_mode, agreement_number=row.agreement_number,
        agreement_accepted_at=row.agreement_accepted_at, plan_name=plan.name if plan else "Unavailable plan",
        billing_cycle=row.billing_cycle, school_count=row.school_count, entitled_schools=count,
        list_amount=row.list_amount, discount_type=row.discount_type,
        discount_value=row.discount_value, discount_amount=row.discount_amount,
        discount_reason=row.discount_reason, tax_mode=row.tax_mode, tax_rate=row.tax_rate,
        tax_amount=row.tax_amount, finalized_amount=row.finalized_amount,
        total_received=row.total_received, balance_amount=row.balance_amount,
        activation_minimum_amount=row.activation_minimum_amount,
        activation_eligible=row.billing_cycle == "trial" or row.total_received >= row.activation_minimum_amount,
        payment_status=row.payment_status, status=row.status, starts_at=row.starts_at,
        expires_at=row.expires_at, grace_until=row.grace_until,
        last_reminder_sent_at=(await db.execute(select(func.max(SubscriptionPaymentReminder.sent_at)).where(SubscriptionPaymentReminder.organization_subscription_id==row.id))).scalar_one_or_none(),
        due_at=row.due_at, notes=row.notes,
        created_at=row.created_at, updated_at=row.updated_at,
    )


async def _latest_key(db: AsyncSession, entitlement_id: UUID) -> SubscriptionActivationKey | None:
    return (await db.execute(select(SubscriptionActivationKey).where(
        SubscriptionActivationKey.subscription_id == entitlement_id
    ).order_by(SubscriptionActivationKey.created_at.desc()).limit(1))).scalar_one_or_none()


async def _school_out(db: AsyncSession, row: SchoolSubscription) -> SchoolSubscriptionOut:
    school = await db.get(School, row.school_id)
    config = (await db.execute(select(SchoolConfiguration).where(
        SchoolConfiguration.school_id == row.school_id
    ))).scalar_one_or_none()
    account = await db.get(OrganizationSubscription, row.organization_subscription_id)
    organization = await db.get(Organization, account.organization_id) if account else None
    plan = await db.get(SubscriptionPlan, row.plan_id) if account else None
    key = await _latest_key(db, row.id)
    now = datetime.now(UTC)
    if row.expires_at < now and row.status != "disabled":
        row.status = "expired"
    return SchoolSubscriptionOut(
        id=row.id, school_id=row.school_id,
        organization_subscription_id=row.organization_subscription_id,
        organization_id=account.organization_id if account else UUID(int=0),
        school_name=config.name if config else (school.code if school else "Unavailable school"),
        school_code=school.code if school else "—",
        organization_name=organization.name if organization else "Unavailable organization",
        plan_id=row.plan_id if account else UUID(int=0),
        plan_name=plan.name if plan else "Unavailable plan",
        billing_cycle=row.billing_cycle if account else "unknown", status=row.status,
        starts_at=row.starts_at, expires_at=row.expires_at,
        days_remaining=max(0, (row.expires_at.date() - now.date()).days),
        activation_status="not_required" if account and account.billing_cycle == "trial" else (key.status if key else "not_generated"),
        activation_key_masked=activation_mask(key.key_last4) if key else None,
        created_at=row.created_at, updated_at=row.updated_at,
    )


async def _reminder_out(db: AsyncSession, row: SubscriptionPaymentReminder) -> ReminderOut:
    account = await db.get(OrganizationSubscription, row.organization_subscription_id)
    organization = await db.get(Organization, account.organization_id) if account else None
    return ReminderOut(
        id=row.id, organization_subscription_id=row.organization_subscription_id,
        organization_admin_id=row.organization_admin_id,
        organization_name=organization.name if organization else "Unavailable organization",
        amount_due=account.balance_amount if account else Decimal("0"),
        due_at=account.due_at if account else None, channel=row.channel, message=row.message,
        delivery_status=row.delivery_status, sent_at=row.sent_at, read_at=row.read_at,
    )


@subscriptions_router.get("/plans", response_model=list[SubscriptionPlanOut])
async def list_plans(db: Annotated[AsyncSession, Depends(get_db)], _user: Annotated[User, Depends(get_current_active_superuser)]):
    return list((await db.execute(select(SubscriptionPlan).order_by(SubscriptionPlan.name))).scalars().all())


@subscriptions_router.post("/plans", response_model=SubscriptionPlanOut, status_code=201)
async def create_plan(payload: SubscriptionPlanCreate, request: Request, db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_active_superuser)]):
    if (await db.execute(select(SubscriptionPlan.id).where(func.lower(SubscriptionPlan.code) == payload.code.lower()))).scalar_one_or_none():
        raise HTTPException(409, "Plan code already exists")
    # Customized plans are created in the catalog before Organization onboarding.
    # Plans are never owned by an Organization; the Organization Subscription performs assignment.
    if payload.organization_id:
        raise HTTPException(422, "Plans cannot be assigned to an Organization while creating the plan")
    data = payload.model_dump()
    data["code"] = payload.code.upper()
    row = SubscriptionPlan(**data, created_by=user.id)
    db.add(row); await db.flush()
    await record_audit(db, action="subscription.plan.created", user=user, module="subscriptions", entity_type="SubscriptionPlan", entity_id=row.id, after={"code": row.code, "name": row.name}, request=request)
    return row


@subscriptions_router.patch("/plans/{plan_id}", response_model=SubscriptionPlanOut)
async def update_plan(plan_id: UUID, payload: SubscriptionPlanUpdate, request: Request, db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_active_superuser)]):
    row = await db.get(SubscriptionPlan, plan_id)
    if not row: raise HTTPException(404, "Plan not found")
    if get_settings().app_env.strip().lower() in {"production", "prod"}:
        raise HTTPException(403, "Plan catalog is locked in production. Create a new plan version instead.")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items(): setattr(row, key, value)
    await db.flush()
    await record_audit(db, action="subscription.plan.updated", user=user, module="subscriptions", entity_type="SubscriptionPlan", entity_id=row.id, after=changes, request=request)
    return row



@subscriptions_router.delete("/plans/{plan_id}", status_code=204)
async def delete_plan(plan_id: UUID, request: Request, db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_active_superuser)]):
    row = await db.get(SubscriptionPlan, plan_id)
    if not row:
        raise HTTPException(404, "Plan not found")
    if row.plan_kind != "custom":
        raise HTTPException(409, "Only customized plans can be deleted")
    assigned_accounts = int((await db.execute(select(func.count(OrganizationSubscription.id)).where(OrganizationSubscription.plan_id == row.id))).scalar_one() or 0)
    assigned_schools = int((await db.execute(select(func.count(SchoolSubscription.id)).join(OrganizationSubscription, OrganizationSubscription.id == SchoolSubscription.organization_subscription_id).where(OrganizationSubscription.plan_id == row.id))).scalar_one() or 0)
    if assigned_accounts or assigned_schools:
        raise HTTPException(409, "Customized plan cannot be deleted while assigned to an Organization or School")
    before = {"code": row.code, "name": row.name, "plan_kind": row.plan_kind}
    await record_audit(db, action="subscription.plan.deleted", user=user, module="subscriptions", entity_type="SubscriptionPlan", entity_id=row.id, before=before, request=request)
    await db.delete(row)
    await db.flush()
    return Response(status_code=204)

@subscriptions_router.post("/accounts", response_model=OrganizationSubscriptionOut, status_code=201)
async def create_account(payload: OrganizationSubscriptionCreate, request: Request, db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_active_superuser)]):
    organization = await db.get(Organization, payload.organization_id)
    plan = await db.get(SubscriptionPlan, payload.plan_id)
    if not organization: raise HTTPException(404, "Organization not found")
    if not plan or not plan.is_active: raise HTTPException(404, "Active plan not found")
    existing = (await db.execute(select(OrganizationSubscription).where(
        OrganizationSubscription.organization_id == organization.id,
        OrganizationSubscription.status.in_(["trial", "pending_payment", "active", "overdue"]),
    ))).scalar_one_or_none()
    if existing: raise HTTPException(409, "Organization already has a current subscription")
    try:
        values = payload.model_dump(exclude={"organization_id", "plan_id"})
        row = await create_organization_subscription(
            db, organization_id=organization.id, plan=plan, created_by=user.id, **values
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    organization.allowed_schools = payload.school_count
    await record_audit(db, action="subscription.account.created", user=user, module="subscriptions", entity_type="OrganizationSubscription", entity_id=row.id, after={"organization_id": str(organization.id), "plan": plan.name, "billing_cycle": row.billing_cycle}, request=request, target_organization_id=organization.id)
    return await _org_account_out(db, row)


@subscriptions_router.get("/accounts", response_model=list[OrganizationSubscriptionOut])
@payments_router.get("/details", response_model=list[OrganizationSubscriptionOut])
async def list_accounts(db: Annotated[AsyncSession, Depends(get_db)], _user: Annotated[User, Depends(get_current_active_superuser)]):
    rows = list((await db.execute(select(OrganizationSubscription).order_by(OrganizationSubscription.created_at.desc()))).scalars().all())
    return [await _org_account_out(db, row) for row in rows]


@subscriptions_router.patch("/accounts/{account_id}", response_model=OrganizationSubscriptionOut)
async def update_account(account_id: UUID, payload: OrganizationSubscriptionUpdate, request: Request, db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_active_superuser)]):
    row = await db.get(OrganizationSubscription, account_id)
    if not row: raise HTTPException(404, "Subscription account not found")
    if row.total_received > 0: raise HTTPException(409, "Financial terms cannot be changed after a payment is recorded")
    changes = payload.model_dump(exclude_unset=True)
    school_count = changes.get("school_count", row.school_count)
    entitled_count = int((await db.execute(select(func.count(SchoolSubscription.id)).where(
        SchoolSubscription.organization_subscription_id == row.id
    ))).scalar_one() or 0)
    if school_count < entitled_count:
        raise HTTPException(422, f"School count cannot be lower than {entitled_count} existing entitlements")
    plan = await db.get(SubscriptionPlan, row.plan_id)
    list_amount = Decimal("0.00") if row.billing_cycle == "trial" else money(
        (plan.monthly_price if row.billing_cycle == "monthly" else plan.yearly_price) * school_count
    )
    discount_type = changes.get("discount_type", row.discount_type)
    discount_value = changes.get("discount_value", row.discount_value)
    discount_reason = changes.get("discount_reason", row.discount_reason)
    if discount_type != "none" and not (discount_reason or "").strip(): raise HTTPException(422, "Discount reason is required")
    tax_mode = changes.get("tax_mode", row.tax_mode); tax_rate = changes.get("tax_rate", row.tax_rate)
    try: discount, tax, finalized = calculate_financials(list_amount, discount_type, discount_value, tax_mode, tax_rate)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    minimum = changes.get("activation_minimum_amount")
    if minimum is None: minimum = money(finalized * Decimal("0.50"))
    if minimum > finalized: raise HTTPException(422, "Activation minimum cannot exceed finalized amount")
    for key, value in changes.items(): setattr(row, key, value)
    row.school_count=school_count; row.list_amount=list_amount; row.discount_type=discount_type; row.discount_value=discount_value; row.discount_amount=discount; row.discount_reason=discount_reason
    row.tax_mode=tax_mode; row.tax_rate=tax_rate; row.tax_amount=tax; row.finalized_amount=finalized; row.balance_amount=finalized; row.activation_minimum_amount=minimum
    organization = await db.get(Organization, row.organization_id)
    organization.allowed_schools = school_count
    refresh_payment_status(row); await db.flush()
    await record_audit(db, action="subscription.account.updated", user=user, module="subscriptions", entity_type="OrganizationSubscription", entity_id=row.id, after=changes, request=request, target_organization_id=row.organization_id)
    return await _org_account_out(db, row)


@payments_router.get("/summary", response_model=PlatformPaymentSummary)
async def payment_summary(db: Annotated[AsyncSession, Depends(get_db)], _user: Annotated[User, Depends(get_current_active_superuser)]):
    accounts = list((await db.execute(select(OrganizationSubscription))).scalars().all())
    for row in accounts: refresh_payment_status(row)
    now = datetime.now(UTC); month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    received_month = (await db.execute(select(func.coalesce(func.sum(SubscriptionPayment.amount), 0)).where(SubscriptionPayment.status == "received", SubscriptionPayment.payment_date >= month_start))).scalar_one()
    return PlatformPaymentSummary(
        total_finalized=money(sum((r.finalized_amount for r in accounts), Decimal("0"))),
        total_received=money(sum((r.total_received for r in accounts), Decimal("0"))),
        outstanding=money(sum((r.balance_amount for r in accounts), Decimal("0"))),
        overdue=money(sum((r.balance_amount for r in accounts if r.payment_status == "overdue"), Decimal("0"))),
        current_month_collection=money(received_month), paid_accounts=sum(r.payment_status == "paid" for r in accounts),
        partial_accounts=sum(r.payment_status == "partially_paid" for r in accounts),
        unpaid_accounts=sum(r.payment_status in {"unpaid", "overdue"} for r in accounts),
    )


@payments_router.post("/details/{account_id}/payments", response_model=SubscriptionPaymentOut, status_code=201)
async def record_payment(account_id: UUID, payload: SubscriptionPaymentCreate, request: Request, db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_active_superuser)]):
    account = await db.get(OrganizationSubscription, account_id)
    if not account: raise HTTPException(404, "Subscription account not found")
    if account.billing_cycle == "trial": raise HTTPException(409, "Trial subscriptions do not require payment")
    amount = money(payload.amount)
    if amount > account.balance_amount: raise HTTPException(422, "Payment cannot exceed the outstanding balance")
    settings = await _settings(db)
    receipt = f"{settings.receipt_prefix}-{datetime.now(UTC):%Y%m%d}-{secrets.token_hex(3).upper()}"
    row = SubscriptionPayment(
        organization_subscription_id=account.id, receipt_number=receipt, amount=amount,
        payment_date=payload.payment_date or datetime.now(UTC), payment_mode=payload.payment_mode,
        reference_number=payload.reference_number, notes=payload.notes, received_by=user.id,
        tax_snapshot={"mode": account.tax_mode, "rate": str(account.tax_rate), "amount": str(account.tax_amount), "gstin": settings.gstin},
    )
    db.add(row); account.total_received=money(account.total_received + amount); account.balance_amount=money(account.finalized_amount-account.total_received)
    refresh_payment_status(account); await db.flush()
    await record_audit(db, action="payment.received", user=user, module="payments", entity_type="SubscriptionPayment", entity_id=row.id, after={"receipt": receipt, "amount": str(amount), "balance": str(account.balance_amount)}, request=request, target_organization_id=account.organization_id)
    return row


@payments_router.get("/receipts", response_model=list[SubscriptionPaymentOut])
async def list_receipts(db: Annotated[AsyncSession, Depends(get_db)], _user: Annotated[User, Depends(get_current_active_superuser)]):
    return list((await db.execute(select(SubscriptionPayment).where(SubscriptionPayment.status == "received").order_by(SubscriptionPayment.payment_date.desc()))).scalars().all())


@payments_router.get("/receipts/{payment_id}", response_model=PaymentReceiptOut)
async def receipt_detail(payment_id: UUID, db: Annotated[AsyncSession, Depends(get_db)], _user: Annotated[User, Depends(get_current_active_superuser)]):
    payment = await db.get(SubscriptionPayment, payment_id)
    if not payment: raise HTTPException(404, "Receipt not found")
    account = await db.get(OrganizationSubscription, payment.organization_subscription_id)
    organization = await db.get(Organization, account.organization_id); plan = await db.get(SubscriptionPlan, account.plan_id)
    settings = await _settings(db)
    return PaymentReceiptOut(
        receipt_number=payment.receipt_number, organization_name=organization.name,
        organization_code=organization.code, school_count=account.school_count, plan_name=plan.name,
        billing_cycle=account.billing_cycle, amount_received=payment.amount,
        payment_date=payment.payment_date, payment_mode=payment.payment_mode,
        reference_number=payment.reference_number, tax_mode=account.tax_mode,
        tax_rate=account.tax_rate, tax_amount=account.tax_amount,
        finalized_amount=account.finalized_amount, total_received=account.total_received,
        balance_amount=account.balance_amount, issuer=SubscriptionBillingSettingsOut.model_validate(settings),
    )


@payments_router.get("/financial-details/{account_id}", response_model=SubscriptionStatementOut)
async def statement(account_id: UUID, db: Annotated[AsyncSession, Depends(get_db)], _user: Annotated[User, Depends(get_current_active_superuser)]):
    account = await db.get(OrganizationSubscription, account_id)
    if not account: raise HTTPException(404, "Subscription account not found")
    payments = list((await db.execute(select(SubscriptionPayment).where(SubscriptionPayment.organization_subscription_id == account.id).order_by(SubscriptionPayment.payment_date))).scalars().all())
    reminders = list((await db.execute(select(SubscriptionPaymentReminder).where(SubscriptionPaymentReminder.organization_subscription_id == account.id).order_by(SubscriptionPaymentReminder.sent_at))).scalars().all())
    schools = list((await db.execute(select(SchoolSubscription).where(SchoolSubscription.organization_subscription_id == account.id))).scalars().all())
    return SubscriptionStatementOut(account=await _org_account_out(db, account), payments=payments, reminders=[await _reminder_out(db, r) for r in reminders], schools=[await _school_out(db, s) for s in schools])


@payments_router.get("/settings", response_model=SubscriptionBillingSettingsOut)
async def get_billing_settings(db: Annotated[AsyncSession, Depends(get_db)], _user: Annotated[User, Depends(get_current_active_superuser)]): return await _settings(db)


@payments_router.patch("/settings", response_model=SubscriptionBillingSettingsOut)
async def update_billing_settings(payload: SubscriptionBillingSettingsUpdate, request: Request, db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_active_superuser)]):
    row=await _settings(db); changes=payload.model_dump(exclude_unset=True)
    for key,value in changes.items(): setattr(row,key,value)
    row.updated_by=user.id; await db.flush()
    await record_audit(db, action="payments.settings.updated", user=user, module="payments", entity_type="SubscriptionBillingSettings", entity_id=None, after=changes, request=request)
    return row


@subscriptions_router.get("/schools", response_model=list[SchoolSubscriptionOut])
async def list_school_entitlements(db: Annotated[AsyncSession, Depends(get_db)], _user: Annotated[User, Depends(get_current_active_superuser)]):
    rows=list((await db.execute(select(SchoolSubscription).order_by(SchoolSubscription.created_at.desc()))).scalars().all())
    return [await _school_out(db,row) for row in rows]


@subscriptions_router.post("/schools/{entitlement_id}/activation-keys", response_model=ActivationKeyGeneratedOut, status_code=201)
async def generate_key(entitlement_id: UUID, payload: ActivationKeyGenerate, request: Request, db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_active_superuser)]):
    entitlement=await db.get(SchoolSubscription,entitlement_id)
    if not entitlement: raise HTTPException(404,"School subscription not found")
    account=await db.get(OrganizationSubscription,entitlement.organization_subscription_id)
    if account.billing_cycle=="trial": raise HTTPException(409,"Trial schools activate automatically and do not use activation keys")
    if account.total_received < account.activation_minimum_amount: raise HTTPException(409,f"Minimum payment of {account.activation_minimum_amount} is required before generating a key")
    existing=await _latest_key(db,entitlement.id)
    if existing and existing.status=="generated" and existing.valid_until>datetime.now(UTC): raise HTTPException(409,"An unused activation key is already valid for this school")
    code=f"SERP-ACT-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
    row=SubscriptionActivationKey(subscription_id=entitlement.id,school_id=entitlement.school_id,key_hash=activation_hash(code),key_last4=code[-4:],status="generated",valid_until=datetime.now(UTC)+timedelta(hours=payload.validity_hours),generated_by=user.id)
    db.add(row); await db.flush()
    await record_audit(db,action="subscription.activation_key.generated",user=user,module="subscriptions",entity_type="SubscriptionActivationKey",entity_id=row.id,after={"school_id":str(row.school_id),"valid_until":row.valid_until.isoformat()},request=request,target_school_id=row.school_id,target_organization_id=account.organization_id)
    return ActivationKeyGeneratedOut(id=row.id,subscription_id=row.subscription_id,school_id=row.school_id,activation_code=code,masked_code=activation_mask(row.key_last4),status=row.status,valid_until=row.valid_until)


@subscriptions_router.get("/schools/{entitlement_id}/activation-keys", response_model=list[ActivationKeyOut])
async def list_keys(entitlement_id: UUID, db: Annotated[AsyncSession, Depends(get_db)], _user: Annotated[User, Depends(get_current_active_superuser)]):
    rows=list((await db.execute(select(SubscriptionActivationKey).where(SubscriptionActivationKey.subscription_id==entitlement_id).order_by(SubscriptionActivationKey.created_at.desc()))).scalars().all())
    return [ActivationKeyOut(id=r.id,subscription_id=r.subscription_id,school_id=r.school_id,masked_code=activation_mask(r.key_last4),status=r.status,valid_until=r.valid_until,generated_by=r.generated_by,activated_at=r.activated_at,activated_by=r.activated_by,revoked_at=r.revoked_at,revocation_reason=r.revocation_reason,created_at=r.created_at) for r in rows]


@subscriptions_router.post("/activation-keys/{key_id}/revoke", response_model=ActivationKeyOut)
async def revoke_key(key_id: UUID,payload:ActivationRevoke,request:Request,db:Annotated[AsyncSession,Depends(get_db)],user:Annotated[User,Depends(get_current_active_superuser)]):
    row=await db.get(SubscriptionActivationKey,key_id)
    if not row: raise HTTPException(404,"Activation key not found")
    if row.status=="activated": raise HTTPException(409,"An activated key cannot be revoked; disable the school instead")
    row.status="revoked";row.revoked_at=datetime.now(UTC);row.revoked_by=user.id;row.revocation_reason=payload.reason;await db.flush()
    entitlement=await db.get(SchoolSubscription,row.subscription_id)
    account=await db.get(OrganizationSubscription,entitlement.organization_subscription_id) if entitlement else None
    await record_audit(db,action="subscription.activation_key.revoked",user=user,module="subscriptions",entity_type="SubscriptionActivationKey",entity_id=row.id,after={"school_id":str(row.school_id),"reason":payload.reason},request=request,target_school_id=row.school_id,target_organization_id=account.organization_id if account else None)
    return ActivationKeyOut(id=row.id,subscription_id=row.subscription_id,school_id=row.school_id,masked_code=activation_mask(row.key_last4),status=row.status,valid_until=row.valid_until,generated_by=row.generated_by,activated_at=row.activated_at,activated_by=row.activated_by,revoked_at=row.revoked_at,revocation_reason=row.revocation_reason,created_at=row.created_at)


@subscriptions_router.get("/activation/terms", response_model=ActivationTermsOut)
async def activation_terms(user: Annotated[User, Depends(get_current_user)]):
    if user.account_type != "ORGANIZATION_ADMIN" or not user.organization_id:
        raise HTTPException(403, "Organization Admin access required")
    settings = get_settings()
    return ActivationTermsOut(
        version=settings.activation_terms_version,
        url=settings.activation_terms_url or None,
    )


@subscriptions_router.post("/activation/activate", response_model=ActivationResult)
async def activate_school(payload:ActivationRequest,request:Request,db:Annotated[AsyncSession,Depends(get_db)],user:Annotated[User,Depends(get_current_user)]):
    if user.account_type!="ORGANIZATION_ADMIN" or not user.organization_id:
        raise HTTPException(403,"Only Organization Admin can activate an ERP school")
    settings = get_settings()
    if not payload.terms_accepted:
        raise HTTPException(422,"Terms & Conditions must be accepted before School activation")
    if payload.terms_version != settings.activation_terms_version:
        raise HTTPException(409,"Terms & Conditions have changed. Review and accept the current version before activation")

    # Lock the commercial and School records so key use, payment eligibility,
    # terms acceptance and activation happen as one transaction.
    school=(await db.execute(select(School).where(School.id==payload.school_id).with_for_update())).scalar_one_or_none()
    if not school or school.organization_id!=user.organization_id:
        raise HTTPException(403,"School is outside your organization")
    organization=(await db.execute(select(Organization).where(Organization.id==school.organization_id).with_for_update())).scalar_one_or_none()
    if not organization or organization.archived_at is not None or not organization.is_active:
        raise HTTPException(409,"Society/Trust must be active before School activation")
    entitlement=(await db.execute(
        select(SchoolSubscription)
        .where(
            SchoolSubscription.school_id==school.id,
            SchoolSubscription.status.in_(["pending_activation","disabled"]),
        )
        .order_by(SchoolSubscription.created_at.desc())
        .limit(1)
        .with_for_update()
    )).scalar_one_or_none()
    if not entitlement:
        raise HTTPException(404,"Pending school subscription not found")
    account=(await db.execute(
        select(OrganizationSubscription)
        .where(OrganizationSubscription.id==entitlement.organization_subscription_id)
        .with_for_update()
    )).scalar_one_or_none()
    if not account:
        raise HTTPException(409,"Organization subscription is unavailable")
    if account.billing_cycle=="trial":
        raise HTTPException(409,"Trial schools do not require activation keys")
    refresh_payment_status(account)
    if account.expires_at <= datetime.now(UTC):
        raise HTTPException(409,"Subscription has expired. Renew it before activation")
    if account.total_received < account.activation_minimum_amount:
        raise HTTPException(409,"Minimum activation payment has not been received")

    key=(await db.execute(
        select(SubscriptionActivationKey)
        .where(
            SubscriptionActivationKey.subscription_id==entitlement.id,
            SubscriptionActivationKey.school_id==school.id,
            SubscriptionActivationKey.key_hash==activation_hash(payload.activation_code),
        )
        .with_for_update()
    )).scalar_one_or_none()
    now=datetime.now(UTC)
    if not key or key.status!="generated" or key.valid_until<now:
        raise HTTPException(422,"Activation key is invalid, expired, already used or revoked")

    plan=await db.get(SubscriptionPlan,entitlement.plan_id)
    license_=(await db.execute(select(SchoolLicense).where(SchoolLicense.school_id==school.id).with_for_update())).scalar_one_or_none()
    if not plan or not license_:
        raise HTTPException(409,"School subscription or license record is unavailable")

    license_.enabled_modules=effective_modules(plan,trial=False)
    license_.max_users=plan.max_users
    license_.starts_at=account.starts_at
    license_.expires_at=(account.grace_until or account.expires_at)
    license_.is_active=True
    school.is_active=True
    entitlement.status="active"
    entitlement.terms_accepted_at=now
    entitlement.terms_accepted_by=user.id
    entitlement.terms_version=payload.terms_version
    entitlement.terms_ip_address=request.client.host if request.client else None
    key.status="activated"
    key.activated_at=now
    key.activated_by=user.id
    # School-scoped users should normally not exist before activation. If legacy
    # rows are present, activation is the point at which they may become active.
    await db.execute(update(User).where(User.school_id==school.id).values(is_active=True))
    await db.flush()
    await record_audit(
        db,
        action="subscription.school.activated",
        user=user,
        module="erp_activation",
        entity_type="SchoolSubscription",
        entity_id=entitlement.id,
        after={
            "school_id":str(school.id),
            "expires_at":entitlement.expires_at.isoformat(),
            "terms_version":payload.terms_version,
            "terms_accepted_at":now.isoformat(),
            "activation_key_id":str(key.id),
            "payment_received":str(account.total_received),
            "activation_minimum_amount":str(account.activation_minimum_amount),
        },
        request=request,
        target_school_id=school.id,
        target_organization_id=school.organization_id,
    )
    return ActivationResult(school_id=school.id,subscription_id=entitlement.id,status="active",plan_name=plan.name,activated_at=now,expires_at=entitlement.expires_at)


@subscriptions_router.get("/activation/my-schools", response_model=list[OrganizationActivationSchoolOut])
async def my_activation_schools(db:Annotated[AsyncSession,Depends(get_db)],user:Annotated[User,Depends(get_current_user)]):
    if user.account_type!="ORGANIZATION_ADMIN" or not user.organization_id: raise HTTPException(403,"Organization Admin access required")
    rows=list((await db.execute(select(SchoolSubscription).join(School,School.id==SchoolSubscription.school_id).where(School.organization_id==user.organization_id,School.deleted_at.is_(None)).order_by(SchoolSubscription.created_at.desc()))).scalars().all())
    result=[]
    for row in rows:
        out=await _school_out(db,row)
        result.append(OrganizationActivationSchoolOut(school_id=out.school_id,school_name=out.school_name,school_code=out.school_code,plan_name=out.plan_name,subscription_status=out.status,activation_status=out.activation_status,expires_at=out.expires_at,days_remaining=out.days_remaining))
    return result


@subscriptions_router.get("/activation/my-reminders", response_model=list[ReminderOut])
async def my_reminders(db:Annotated[AsyncSession,Depends(get_db)],user:Annotated[User,Depends(get_current_user)]):
    if user.account_type!="ORGANIZATION_ADMIN": raise HTTPException(403,"Organization Admin access required")
    rows=list((await db.execute(select(SubscriptionPaymentReminder).where(SubscriptionPaymentReminder.organization_admin_id==user.id).order_by(SubscriptionPaymentReminder.sent_at.desc()))).scalars().all())
    return [await _reminder_out(db,row) for row in rows]


@subscriptions_router.post("/accounts/{account_id}/reminders", response_model=ReminderOut, status_code=201)
async def send_reminder(account_id:UUID,payload:ReminderCreate,request:Request,db:Annotated[AsyncSession,Depends(get_db)],user:Annotated[User,Depends(get_current_active_superuser)]):
    account=await db.get(OrganizationSubscription,account_id)
    if not account: raise HTTPException(404,"Subscription account not found")
    admin=(await db.execute(select(User).where(User.organization_id==account.organization_id,User.account_type=="ORGANIZATION_ADMIN",User.school_id.is_(None),User.is_active.is_(True)).order_by(User.created_at).limit(1))).scalar_one_or_none()
    if not admin: raise HTTPException(409,"No active Organization Admin is available for reminders")
    organization=await db.get(Organization,account.organization_id)
    message=payload.message or f"Payment reminder for {organization.name}: balance {account.balance_amount} is due" + (f" on {account.due_at.date().isoformat()}" if account.due_at else "") + "."
    row=SubscriptionPaymentReminder(organization_subscription_id=account.id,organization_admin_id=admin.id,channel="in_app",message=message,delivery_status="sent",sent_by=user.id)
    db.add(row);await db.flush()
    await record_audit(db,action="subscription.reminder.sent",user=user,module="subscriptions",entity_type="SubscriptionPaymentReminder",entity_id=row.id,after={"organization_admin_id":str(admin.id)},request=request,target_organization_id=account.organization_id)
    return await _reminder_out(db,row)


@subscriptions_router.post("/schools/{entitlement_id}/disable", response_model=SchoolSubscriptionOut)
async def disable_school(entitlement_id:UUID,payload:SchoolSubscriptionDisable,request:Request,db:Annotated[AsyncSession,Depends(get_db)],user:Annotated[User,Depends(get_current_active_superuser)]):
    row=await db.get(SchoolSubscription,entitlement_id)
    if not row: raise HTTPException(404,"School subscription not found")
    account=await db.get(OrganizationSubscription,row.organization_subscription_id)
    reminder_count=int((await db.execute(select(func.count(SubscriptionPaymentReminder.id)).where(
        SubscriptionPaymentReminder.organization_subscription_id==row.organization_subscription_id
    ))).scalar_one() or 0)
    if account and account.balance_amount>0 and reminder_count==0:
        raise HTTPException(409,"Send a payment reminder to the Organization Admin before disabling this school")
    school=await db.get(School,row.school_id);license_=(await db.execute(select(SchoolLicense).where(SchoolLicense.school_id==row.school_id))).scalar_one_or_none()
    row.status="disabled";school.is_active=False
    if license_: license_.is_active=False
    await revoke_school_sessions(db,row.school_id);await db.flush()
    await record_audit(db,action="subscription.school.disabled",user=user,module="subscriptions",entity_type="SchoolSubscription",entity_id=row.id,after={"school_id":str(row.school_id),"reason":payload.reason},request=request,target_school_id=row.school_id,target_organization_id=school.organization_id)
    return await _school_out(db,row)


@subscriptions_router.post("/accounts/{account_id}/renew", response_model=OrganizationSubscriptionOut)
async def renew_account(account_id:UUID,payload:SubscriptionRenewalRequest,request:Request,db:Annotated[AsyncSession,Depends(get_db)],user:Annotated[User,Depends(get_current_active_superuser)]):
    account=await db.get(OrganizationSubscription,account_id)
    if not account: raise HTTPException(404,"Subscription account not found")
    if account.billing_cycle=="trial": raise HTTPException(409,"Convert a trial to a paid plan instead of renewing it")
    if account.balance_amount>0: raise HTTPException(409,"Complete the current cycle payment before renewal")
    base=payload.renewal_start_date
    if base.tzinfo is None: base=base.replace(tzinfo=UTC)
    old={"starts_at":account.starts_at.isoformat(),"expires_at":account.expires_at.isoformat(),"grace_until":account.grace_until.isoformat() if account.grace_until else None}
    account.starts_at=base;account.expires_at=expiry_for(base,account.billing_cycle);account.grace_until=grace_until_for(account.expires_at,account.billing_cycle)
    account.total_received=Decimal("0.00");account.balance_amount=account.finalized_amount;account.payment_status="unpaid";account.status="pending_payment";account.due_at=base
    entitlements=list((await db.execute(select(SchoolSubscription).where(SchoolSubscription.organization_subscription_id==account.id))).scalars().all())
    for item in entitlements:
        item.starts_at=base;item.expires_at=(account.grace_until or account.expires_at)
        if item.status in {"active","expiring"}: item.status="active"
        license_=(await db.execute(select(SchoolLicense).where(SchoolLicense.school_id==item.school_id))).scalar_one_or_none()
        if license_ and license_.is_active: license_.starts_at=base;license_.expires_at=(account.grace_until or account.expires_at)
    await db.flush()
    await record_audit(db,action="subscription.renewed",user=user,module="subscriptions",entity_type="OrganizationSubscription",entity_id=account.id,before=old,after={"starts_at":account.starts_at.isoformat(),"expires_at":account.expires_at.isoformat(),"grace_until":account.grace_until.isoformat() if account.grace_until else None,"communicated_with":payload.communicated_with,"communication_method":payload.communication_method,"remarks":payload.remarks},request=request,target_organization_id=account.organization_id)
    return await _org_account_out(db,account)


@subscriptions_router.post("/accounts/{account_id}/extend", response_model=OrganizationSubscriptionOut)
async def extend_account(account_id:UUID,payload:SubscriptionExtensionRequest,request:Request,db:Annotated[AsyncSession,Depends(get_db)],user:Annotated[User,Depends(get_current_active_superuser)]):
    account=await db.get(OrganizationSubscription,account_id)
    if not account: raise HTTPException(404,"Subscription account not found")
    if account.billing_cycle=="trial": raise HTTPException(409,"Trial cannot be extended; convert it to a paid plan")
    new_end=payload.new_end_date
    if new_end.tzinfo is None: new_end=new_end.replace(tzinfo=UTC)
    if new_end <= account.expires_at: raise HTTPException(422,"New end date must be after the current end date")
    old_end=account.expires_at;old_grace=account.grace_until
    account.expires_at=new_end;account.grace_until=grace_until_for(new_end,account.billing_cycle)
    entitlements=list((await db.execute(select(SchoolSubscription).where(SchoolSubscription.organization_subscription_id==account.id))).scalars().all())
    for item in entitlements:
        item.expires_at=(account.grace_until or new_end)
        license_=(await db.execute(select(SchoolLicense).where(SchoolLicense.school_id==item.school_id))).scalar_one_or_none()
        if license_: license_.expires_at=(account.grace_until or new_end)
    await db.flush()
    await record_audit(db,action="subscription.expiry.extended",user=user,module="subscriptions",entity_type="OrganizationSubscription",entity_id=account.id,before={"expires_at":old_end.isoformat(),"grace_until":old_grace.isoformat() if old_grace else None},after={"expires_at":new_end.isoformat(),"grace_until":account.grace_until.isoformat(),"reason":payload.reason,"communicated_with":payload.communicated_with,"communication_method":payload.communication_method,"remarks":payload.remarks},request=request,target_organization_id=account.organization_id)
    return await _org_account_out(db,account)


@subscriptions_router.post("/accounts/{account_id}/convert-trial", response_model=OrganizationSubscriptionOut)
async def convert_trial(account_id:UUID,payload:TrialConversion,request:Request,db:Annotated[AsyncSession,Depends(get_db)],user:Annotated[User,Depends(get_current_active_superuser)]):
    account=await db.get(OrganizationSubscription,account_id)
    if not account: raise HTTPException(404,"Subscription account not found")
    if account.billing_cycle!="trial": raise HTTPException(409,"Only a trial account can be converted")
    plan=await db.get(SubscriptionPlan,payload.plan_id)
    if not plan or not plan.is_active: raise HTTPException(404,"Active paid plan not found")
    if plan.code.upper()=="TRIAL": raise HTTPException(409,"Choose a paid plan when converting a trial")
    if payload.due_at is None: raise HTTPException(422,"Payment Due Date is required when converting Trial to a paid plan")
    if payload.discount_type != "none" and not (payload.discount_reason or "").strip(): raise HTTPException(422,"Discount reason is required when a discount is applied")
    account.school_count=payload.school_count
    organization=await db.get(Organization,account.organization_id)
    if organization:
        organization.allowed_schools=payload.school_count
    list_amount=money((plan.monthly_price if payload.billing_cycle=="monthly" else plan.yearly_price)*account.school_count)
    try: discount,tax,finalized=calculate_financials(list_amount,payload.discount_type,payload.discount_value,payload.tax_mode,payload.tax_rate)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    calculated_minimum=money(finalized*Decimal("0.50"))
    minimum=money(payload.activation_minimum_amount if payload.activation_minimum_amount is not None else calculated_minimum)
    if minimum>finalized: raise HTTPException(422,"Activation minimum cannot exceed finalized amount")
    if minimum<calculated_minimum and not (payload.activation_override_reason or "").strip(): raise HTTPException(422,"Reason is required when Minimum Activation Payment is below the calculated minimum")
    now=datetime.now(UTC);account.plan_id=plan.id;account.billing_cycle=payload.billing_cycle;account.list_amount=list_amount;account.discount_type=payload.discount_type;account.discount_value=money(payload.discount_value);account.discount_amount=discount;account.discount_reason=payload.discount_reason;account.tax_mode=payload.tax_mode;account.tax_rate=money(payload.tax_rate);account.tax_amount=tax;account.finalized_amount=finalized;account.total_received=Decimal("0.00");account.balance_amount=finalized;account.activation_minimum_amount=minimum;account.payment_status="unpaid";account.status="pending_payment";account.starts_at=now;account.expires_at=expiry_for(now,payload.billing_cycle,plan.trial_days);account.grace_until=grace_until_for(account.expires_at,payload.billing_cycle);account.due_at=payload.due_at;account.notes=payload.notes;account.activation_minimum_original=calculated_minimum;account.activation_override_used=minimum<calculated_minimum;account.activation_override_reason=payload.activation_override_reason.strip() if minimum<calculated_minimum and payload.activation_override_reason else None;account.activation_overridden_by=user.id if minimum<calculated_minimum else None;account.activation_overridden_at=now if minimum<calculated_minimum else None
    entitlements=list((await db.execute(select(SchoolSubscription).where(SchoolSubscription.organization_subscription_id==account.id))).scalars().all())
    for item in entitlements:
        item.status="pending_activation";item.plan_id=plan.id;item.billing_cycle=payload.billing_cycle;item.base_student_capacity=plan.student_limit;item.approved_extra_capacity=0;item.plan_snapshot={"plan_id":str(plan.id),"code":plan.code,"name":plan.name,"student_limit":plan.student_limit,"teacher_limit":plan.teacher_limit,"enabled_modules":list(plan.enabled_modules or []),"monthly_price":str(plan.monthly_price),"yearly_price":str(plan.yearly_price)};item.starts_at=now;item.expires_at=(account.grace_until or account.expires_at)
        school=await db.get(School,item.school_id);school.is_active=False
        license_=(await db.execute(select(SchoolLicense).where(SchoolLicense.school_id==item.school_id))).scalar_one_or_none()
        if license_: license_.enabled_modules=effective_modules(plan,trial=False);license_.max_users=plan.max_users;license_.starts_at=now;license_.expires_at=(account.grace_until or account.expires_at);license_.is_active=False
        await revoke_school_sessions(db,item.school_id)
    await db.flush()
    await record_audit(db,action="subscription.trial.converted",user=user,module="subscriptions",entity_type="OrganizationSubscription",entity_id=account.id,before={"billing_cycle":"trial","status":"trial","school_count":1},after={"plan_id":str(plan.id),"plan_name":plan.name,"billing_cycle":payload.billing_cycle,"school_count":account.school_count,"converted_at":now.isoformat(),"finalized_amount":str(finalized),"activation_minimum_amount":str(minimum),"activation_minimum_original":str(calculated_minimum),"activation_override_used":minimum<calculated_minimum,"activation_override_reason":account.activation_override_reason,"due_at":account.due_at.isoformat() if account.due_at else None,"notes":payload.notes},request=request,target_organization_id=account.organization_id)
    return await _org_account_out(db,account)


# Backward-compatible import name used by the API router.
router = payments_router
