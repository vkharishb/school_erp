from datetime import UTC, datetime, time, timedelta, timezone
import secrets
import string
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.deps import (
    ensure_organization_access,
    ensure_organization_read_access,
    get_current_active_superuser,
    get_role_codes,
    require_permissions,
)
from app.core.erp_codes import format_organization_code, school_prefix
from app.core.security import get_password_hash
from app.core.usernames import normalize_username
from app.db.session import get_db
from app.models.academic import Student
from app.models.attendance import StudentAttendance, TeacherAttendance
from app.models.fee import Payment, PaymentAllocation, StudentCharge
from app.models.marks import StudentMark
from app.models.organization import (
    AcademicYear,
    Campus,
    Organization,
    OrganizationAcademicYear,
)
from app.models.school import School, SchoolConfiguration
from app.models.staff import Teacher
from app.models.subscription import OrganizationSubscription, SubscriptionPlan
from app.models.user import Role, User, UserRole
from app.schemas.foundation import (
    AcademicYearCreate,
    AcademicYearUpdate,
    OrganizationAcademicYearOut,
    OrganizationCreate,
    OrganizationDashboardOut,
    OrganizationDashboardUnit,
    OrganizationLicenseUpdate,
    OrganizationOut,
    OrganizationStatusUpdate,
    OrganizationUpdate,
)
from app.schemas.school import SchoolOut
from app.services.audit import record_audit
from app.services.backups import has_recent_successful_backup
from app.services.corrections import consume_annual_correction
from app.services.licensing import (
    IMPLEMENTED_MODULES,
    next_may_31,
)
from app.services.password_policy import validate_password
from app.services.session_control import revoke_organization_sessions
from app.services.subscriptions import create_organization_subscription, effective_modules
from app.services.transactional_email import send_transactional_email

router = APIRouter(prefix="/organizations", tags=["Organizations"])

def _temporary_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    while True:
        value = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.islower() for c in value) and any(c.isupper() for c in value) and any(c.isdigit() for c in value) and any(c in "!@#$%&*" for c in value):
            return value

async def _latest_subscription(db: AsyncSession, organization_id: UUID) -> OrganizationSubscription | None:
    return (await db.execute(select(OrganizationSubscription).where(OrganizationSubscription.organization_id == organization_id).order_by(OrganizationSubscription.created_at.desc()).limit(1))).scalar_one_or_none()


async def _next_organization_code(db: AsyncSession, name: str) -> str:
    prefix = school_prefix(name)
    result = await db.execute(
        select(Organization.code).where(Organization.code.like(f"{prefix}-ORG-%"))
    )
    numbers: list[int] = []
    for code in result.scalars().all():
        try:
            numbers.append(int(str(code).rsplit("-", 1)[1]))
        except (ValueError, IndexError):
            continue
    return format_organization_code(prefix, max(numbers, default=0) + 1)


def _organization_out(organization: Organization, admin: User | None = None) -> OrganizationOut:
    return OrganizationOut.model_validate(organization).model_copy(
        update={
            "admin_username": admin.username if admin else None,
            "admin_email": admin.email if admin else None,
            "admin_full_name": admin.full_name if admin else None,
            "admin_phone": admin.phone if admin else None,
            "admin_designation": admin.designation if admin else None,
        }
    )


async def _organization_admin_map(
    db: AsyncSession, organization_ids: list[UUID]
) -> dict[UUID, User]:
    if not organization_ids:
        return {}
    result = await db.execute(
        select(User)
        .where(
            User.organization_id.in_(organization_ids),
            User.account_type == "ORGANIZATION_ADMIN",
            User.school_id.is_(None),
        )
        .order_by(User.is_active.desc(), User.created_at)
    )
    admins: dict[UUID, User] = {}
    for admin in result.scalars().all():
        if admin.organization_id:
            admins.setdefault(admin.organization_id, admin)
    return admins


async def _organization_out_for_db(db: AsyncSession, organization: Organization) -> OrganizationOut:
    admins = await _organization_admin_map(db, [organization.id])
    return _organization_out(organization, admins.get(organization.id))


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(get_current_active_superuser)],
):
    admin_username = normalize_username(payload.admin_username)
    admin_email = normalize_username(str(payload.admin_email))
    duplicate_user = await db.execute(
        select(User.id).where(
            or_(
                func.lower(User.username) == admin_username,
                (
                    (User.account_type == "ORGANIZATION_ADMIN")
                    & or_(
                        func.lower(User.username) == admin_email,
                        func.lower(User.email).in_([admin_username, admin_email]),
                    )
                ),
            )
        )
    )
    if duplicate_user.scalars().first():
        raise HTTPException(
            status_code=409, detail="Organization Admin username or email already exists"
        )
    temporary_password = _temporary_password()
    validate_password(temporary_password, username=admin_username)
    code = await _next_organization_code(db, payload.name)
    now = datetime.now(UTC)
    selected_plan = None
    if not payload.subscription_plan_id or not payload.billing_cycle:
        raise HTTPException(status_code=422, detail="Plan or 30-Day Trial is mandatory for every Organization")
    if payload.subscription_plan_id:
        selected_plan = await db.get(SubscriptionPlan, payload.subscription_plan_id)
        if not selected_plan or not selected_plan.is_active:
            raise HTTPException(status_code=404, detail="Active subscription plan not found")
        plan_code = selected_plan.code.upper()
        if plan_code in {"BASIC", "STANDARD", "PREMIUM"} and payload.billing_cycle != "yearly":
            raise HTTPException(status_code=422, detail=f"{selected_plan.name} is yearly only")
        if plan_code in {"CUSTOMIZED", "PAYG"} and payload.billing_cycle not in {"monthly", "yearly"}:
            raise HTTPException(status_code=422, detail="Customized supports monthly or yearly billing")
    effective_school_limit = 1 if selected_plan and selected_plan.code.upper() == "TRIAL" else payload.allowed_schools
    organization = Organization(
        code=code,
        name=payload.name.strip(),
        allowed_schools=effective_school_limit,
        head_full_name=payload.head_full_name.strip(),
        head_email=str(payload.head_email),
        head_phone=payload.head_phone,
        enabled_modules=effective_modules(selected_plan, trial=selected_plan.code.upper() == "TRIAL") if selected_plan else [],
        license_starts_at=None if selected_plan else now,
        license_expires_at=None if selected_plan else next_may_31(now),
    )
    db.add(organization)
    await db.flush()

    role_result = await db.execute(
        select(Role).where(Role.code == "ORGANIZATION_ADMIN", Role.school_id.is_(None))
    )
    role = role_result.scalars().first()
    if not role:
        raise HTTPException(
            status_code=500, detail="Organization Admin system role is not initialized"
        )
    admin = User(
        username=admin_username,
        account_type="ORGANIZATION_ADMIN",
        email=admin_email,
        hashed_password=get_password_hash(temporary_password),
        full_name=payload.head_full_name.strip(),
        designation=payload.admin_designation,
        phone=payload.head_phone,
        organization_id=organization.id,
        school_id=None,
        campus_id=None,
        is_superuser=False,
        is_active=True,
        must_change_password=True,
    )
    db.add(admin)
    await db.flush()
    db.add(UserRole(user_id=admin.id, role_id=role.id))
    await db.flush()
    subscription = None
    if selected_plan and payload.billing_cycle:
        try:
            subscription = await create_organization_subscription(
                db,
                organization_id=organization.id,
                plan=selected_plan,
                billing_cycle=payload.billing_cycle,
                school_count=effective_school_limit,
                discount_type=payload.discount_type,
                discount_value=payload.discount_value,
                discount_reason=payload.discount_reason,
                tax_mode=payload.tax_mode,
                tax_rate=payload.tax_rate,
                activation_minimum_amount=payload.activation_minimum_amount,
                activation_override_reason=payload.activation_override_reason,
                activation_overridden_by=actor.id,
                due_at=payload.payment_due_at,
                notes=payload.subscription_notes,
                created_by=actor.id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    await record_audit(
        db,
        action="organization.created",
        user=actor,
        module="society_trust",
        entity_type="Organization",
        entity_id=organization.id,
        after={
            "code": organization.code,
            "name": organization.name,
            "allowed_schools": organization.allowed_schools,
            "organization_admin_username": admin.username,
            "organization_admin_email": admin.email,
            "organization_admin_designation": admin.designation,
            "subscription_id": str(subscription.id) if subscription else None,
            "subscription_plan": selected_plan.name if selected_plan else None,
            "billing_cycle": subscription.billing_cycle if subscription else None,
        },
        request=request,
        target_organization_id=organization.id,
    )
    email_ok, email_error = send_transactional_email(
        to_email=admin.email or organization.head_email or "",
        subject="School ERP account created",
        body=f"Your Society/Trust ERP account is ready. Login email: {admin.email}. Username: {admin.username}. Login: {get_settings().frontend_login_url}. Contact the Platform Owner for the temporary password.",
    )
    result = _organization_out(organization, admin)
    return result.model_copy(update={"temporary_password": temporary_password, "email_delivery_status": "sent" if email_ok else f"failed: {email_error}"})



@router.post("/{organization_id}/admin/reset-temporary-password")
async def reset_organization_admin_temporary_password(
    organization_id: UUID, request: Request, db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(get_current_active_superuser)],
):
    admins = await _organization_admin_map(db, [organization_id])
    admin = admins.get(organization_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Organization Admin not found")
    temporary_password = _temporary_password()
    validate_password(temporary_password, username=admin.username)
    admin.hashed_password = get_password_hash(temporary_password)
    admin.must_change_password = True
    revoked = await revoke_organization_sessions(db, organization_id)
    await record_audit(db, action="organization_admin.temporary_password.reset", user=actor, module="society_trust", entity_type="User", entity_id=admin.id, after={"must_change_password": True}, metadata={"sessions_revoked": revoked}, request=request, target_organization_id=organization_id)
    await db.flush()
    return {"temporary_password": temporary_password, "username": admin.username, "email": admin.email}


@router.post("/{organization_id}/admin/resend-email")
async def resend_organization_admin_email(
    organization_id: UUID, request: Request, db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(get_current_active_superuser)],
):
    organization = await db.get(Organization, organization_id)
    admins = await _organization_admin_map(db, [organization_id])
    admin = admins.get(organization_id)
    if not organization or not admin or not admin.email:
        raise HTTPException(status_code=404, detail="Society/Trust or Organization Admin email not found")
    ok, error = send_transactional_email(to_email=admin.email, subject="School ERP account information", body=f"Your Society/Trust ERP login email is {admin.email}; username is {admin.username}. Login: {get_settings().frontend_login_url}. Contact the Platform Owner if a new temporary password is required.")
    await record_audit(db, action="organization_admin.email.resent", user=actor, module="society_trust", entity_type="User", entity_id=admin.id, after={"delivery_status": "sent" if ok else "failed"}, metadata={"error": error} if error else None, request=request, target_organization_id=organization_id)
    if not ok:
        raise HTTPException(status_code=503, detail=f"Email delivery failed: {error}")
    return {"status": "sent"}

@router.get("", response_model=list[OrganizationOut])
async def list_organizations(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("organization.view"))],
    include_archived: bool = False,
):
    if user.is_superuser:
        query = select(Organization)
        if not include_archived:
            query = query.where(Organization.archived_at.is_(None))
        query = query.order_by(Organization.name)
    elif user.organization_id:
        query = select(Organization).where(
            Organization.id == user.organization_id, Organization.archived_at.is_(None)
        )
    else:
        return []
    result = await db.execute(query)
    organizations = list(result.scalars().all())
    include_admin_login = user.is_superuser or user.account_type == "ORGANIZATION_ADMIN"
    admins = (
        await _organization_admin_map(db, [organization.id for organization in organizations])
        if include_admin_login
        else {}
    )
    return [
        _organization_out(organization, admins.get(organization.id))
        for organization in organizations
    ]


@router.get("/{organization_id}", response_model=OrganizationOut)
async def get_organization(
    organization_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("organization.view"))],
):
    await ensure_organization_access(user, organization_id)
    organization = await db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    if user.is_superuser or user.account_type == "ORGANIZATION_ADMIN":
        return await _organization_out_for_db(db, organization)
    return _organization_out(organization)


@router.patch("/{organization_id}", response_model=OrganizationOut)
async def update_organization(
    organization_id: UUID,
    payload: OrganizationUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("organization.edit"))],
):
    await ensure_organization_access(user, organization_id)
    organization = await db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    if organization.archived_at is not None:
        raise HTTPException(
            status_code=409, detail="Archived Organization is read-only. Restore it before editing."
        )
    changes = payload.model_dump(exclude_unset=True)
    capacity_effective_at = changes.pop("capacity_effective_at", None)
    capacity_reason = changes.pop("capacity_reason", None)
    capacity_discount_type = changes.pop("capacity_discount_type", "none")
    capacity_discount_value = Decimal(str(changes.pop("capacity_discount_value", 0) or 0))
    capacity_discount_reason = changes.pop("capacity_discount_reason", None)
    if not changes:
        return await _organization_out_for_db(db, organization)
    if not user.is_superuser and "allowed_schools" in changes:
        raise HTTPException(
            status_code=403, detail="Only Super Admin can change the allowed number of Schools"
        )
    if "allowed_schools" in changes:
        # Capacity is a commercial limit, not an activation count. Trial is always
        # fixed at one School. A paid limit may be increased only after every
        # currently approved School slot is already consumed.
        from app.models.subscription import OrganizationSubscription

        current_subscription = (
            await db.execute(
                select(OrganizationSubscription).where(
                    OrganizationSubscription.organization_id == organization.id,
                    OrganizationSubscription.status.in_(["trial", "pending_payment", "active", "overdue"]),
                )
            )
        ).scalar_one_or_none()
        requested_limit = int(changes["allowed_schools"])
        school_count = int((await db.execute(
            select(func.count(School.id)).where(
                School.organization_id == organization.id,
                School.deleted_at.is_(None),
            )
        )).scalar_one() or 0)
        if current_subscription and current_subscription.billing_cycle == "trial":
            if requested_limit != 1:
                raise HTTPException(status_code=409, detail="Trial School limit is fixed at 1. Convert the Trial to a paid plan before increasing capacity.")
            requested_limit = 1
            changes["allowed_schools"] = 1
            current_subscription.school_count = 1
        else:
            current_limit = current_subscription.school_count if current_subscription else organization.allowed_schools
            if requested_limit > current_limit and school_count < current_limit:
                raise HTTPException(status_code=409, detail=f"Increase Limit is available only after the current School capacity is exhausted ({school_count}/{current_limit}).")
            if requested_limit < school_count:
                raise HTTPException(status_code=409, detail=f"School limit cannot be lower than the {school_count} existing Schools.")
            if requested_limit > current_limit:
                if not current_subscription:
                    raise HTTPException(status_code=409, detail="A paid subscription is required before School capacity can be increased")
                if current_subscription.billing_cycle == "trial":
                    raise HTTPException(status_code=409, detail="Trial School limit is fixed at 1. Convert the Trial to a paid plan first.")
                if not capacity_effective_at:
                    raise HTTPException(status_code=422, detail="Capacity Effective Date is required")
                if not (capacity_reason or "").strip():
                    raise HTTPException(status_code=422, detail="Capacity increase reason is required")
                effective_at = capacity_effective_at
                if effective_at.tzinfo is None:
                    effective_at = effective_at.replace(tzinfo=UTC)
                if effective_at < current_subscription.starts_at or effective_at > current_subscription.expires_at:
                    raise HTTPException(status_code=422, detail="Capacity Effective Date must fall within the current subscription term")
                added = requested_limit - current_limit
                term_seconds = max((current_subscription.expires_at - current_subscription.starts_at).total_seconds(), 1)
                remaining_seconds = max((current_subscription.expires_at - effective_at).total_seconds(), 0)
                proration = Decimal(str(remaining_seconds / term_seconds))
                unit_amount = (current_subscription.list_amount / Decimal(max(current_limit, 1)))
                incremental_list = (unit_amount * Decimal(added) * proration).quantize(Decimal("0.01"))
                if capacity_discount_type == "percent":
                    incremental_discount = (incremental_list * capacity_discount_value / Decimal("100")).quantize(Decimal("0.01"))
                elif capacity_discount_type == "fixed":
                    incremental_discount = capacity_discount_value.quantize(Decimal("0.01"))
                else:
                    incremental_discount = Decimal("0.00")
                if incremental_discount > incremental_list:
                    raise HTTPException(status_code=422, detail="Capacity discount cannot exceed the incremental charge")
                incremental_taxable = incremental_list - incremental_discount
                incremental_tax = (incremental_taxable * current_subscription.tax_rate / Decimal("100")).quantize(Decimal("0.01")) if current_subscription.tax_mode == "gst" else Decimal("0.00")
                incremental_finalized = incremental_taxable + incremental_tax
                current_subscription.list_amount += incremental_list
                current_subscription.discount_amount += incremental_discount
                current_subscription.tax_amount += incremental_tax
                current_subscription.finalized_amount += incremental_finalized
                current_subscription.balance_amount += incremental_finalized
                current_subscription.school_count = requested_limit
                await record_audit(
                    db,
                    action="subscription.capacity.increased",
                    user=user,
                    module="subscriptions",
                    entity_type="OrganizationSubscription",
                    entity_id=current_subscription.id,
                    before={"school_count": current_limit},
                    after={
                        "school_count": requested_limit,
                        "added_schools": added,
                        "effective_at": effective_at.isoformat(),
                        "incremental_list_amount": str(incremental_list),
                        "incremental_discount": str(incremental_discount),
                        "incremental_tax": str(incremental_tax),
                        "incremental_finalized_amount": str(incremental_finalized),
                        "reason": capacity_reason.strip(),
                        "discount_type": capacity_discount_type,
                        "discount_value": str(capacity_discount_value),
                        "discount_reason": (capacity_discount_reason or "").strip() or None,
                    },
                    request=request,
                    target_organization_id=organization.id,
                )
            elif current_subscription:
                current_subscription.school_count = requested_limit
    if not user.is_superuser:
        await consume_annual_correction(
            db,
            request,
            user,
            organization_id=organization.id,
            entity_type="organization",
            entity_id=organization.id,
        )
    before = {field: getattr(organization, field) for field in changes}
    for field, value in changes.items():
        setattr(organization, field, value)
    await db.flush()
    await record_audit(
        db,
        action="organization.updated",
        user=user,
        module="society_trust",
        entity_type="Organization",
        entity_id=organization.id,
        before=before,
        after=changes,
        request=request,
        target_organization_id=organization.id,
    )
    return await _organization_out_for_db(db, organization)


@router.patch("/{organization_id}/status", response_model=OrganizationOut)
async def set_organization_status(
    organization_id: UUID,
    payload: OrganizationStatusUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_superuser)],
):
    organization = await db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    if organization.archived_at is not None:
        raise HTTPException(status_code=409, detail="Archived Society/Trust cannot be enabled or disabled. Restore it first.")
    subscription = await _latest_subscription(db, organization.id)
    now = datetime.now(UTC)
    if (
        subscription
        and subscription.expires_at > now
        and not payload.is_active
        and not payload.emergency_override
    ):
        raise HTTPException(
            status_code=409,
            detail="Active subscriptions can be suspended only with the Platform Owner emergency override and a mandatory reason",
        )
    if not payload.reason.strip():
        raise HTTPException(status_code=422, detail="Reason is required")
    before = {"is_active": organization.is_active}
    organization.is_active = payload.is_active
    revoked_sessions = 0
    if not payload.is_active:
        organization.disabled_at = now
        organization.disabled_by = user.id
        organization.disable_reason = payload.reason.strip()
        # Organization disable is a reversible access suspension. Child School
        # status/data is deliberately left unchanged so re-enable restores the
        # exact prior operational state rather than guessing which Schools were active.
        revoked_sessions = await revoke_organization_sessions(db, organization.id)
    if payload.is_active:
        organization.disabled_at = None
        organization.disabled_by = None
        organization.disable_reason = None
    await record_audit(
        db,
        action="organization.enabled" if payload.is_active else "organization.disabled",
        user=user,
        module="society_trust",
        entity_type="Organization",
        entity_id=organization.id,
        before=before,
        after={"is_active": organization.is_active},
        metadata={
            "sessions_revoked": revoked_sessions,
            "reason": payload.reason.strip(),
            "emergency_override": bool(payload.emergency_override and not payload.is_active),
        },
        request=request,
        target_organization_id=organization.id,
    )
    await db.flush()
    return await _organization_out_for_db(db, organization)


@router.post("/{organization_id}/archive", response_model=OrganizationOut)
async def archive_organization(
    organization_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_superuser)],
):
    organization = await db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    if organization.archived_at is not None:
        raise HTTPException(status_code=409, detail="Organization is already archived")
    subscription = await _latest_subscription(db, organization.id)
    now = datetime.now(UTC)
    if not subscription or now < subscription.expires_at + timedelta(days=90):
        raise HTTPException(status_code=409, detail="Archive is available only 3 months after subscription expiry")
    archive_settings = get_settings()
    if archive_settings.require_recent_backup_for_archive and not has_recent_successful_backup(
        archive_settings.archive_backup_max_age_hours
    ):
        raise HTTPException(
            status_code=409,
            detail=f"A successful database backup from the last {archive_settings.archive_backup_max_age_hours} hours is required before archiving an Organization.",
        )
    before = {"is_active": organization.is_active, "archived_at": None}
    organization.archived_at = now
    organization.archived_by = user.id
    organization.is_active = False
    revoked = await revoke_organization_sessions(
        db, organization.id, reason="organization_archived"
    )
    await record_audit(
        db,
        action="organization.archived",
        user=user,
        module="society_trust",
        entity_type="Organization",
        entity_id=organization.id,
        before=before,
        after={"is_active": False, "archived_at": now.isoformat()},
        metadata={"sessions_revoked": revoked},
        request=request,
        target_organization_id=organization.id,
    )
    await db.flush()
    return await _organization_out_for_db(db, organization)


@router.post("/{organization_id}/restore", response_model=OrganizationOut)
async def restore_organization(
    organization_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_superuser)],
):
    organization = await db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    if organization.archived_at is None:
        raise HTTPException(status_code=409, detail="Organization is not archived")
    before = {
        "is_active": organization.is_active,
        "archived_at": organization.archived_at.isoformat(),
    }
    organization.archived_at = None
    organization.archived_by = None
    # Restore returns the Organization to a safe disabled state. Platform Owner
    # explicitly enables it after reviewing license and School status.
    organization.is_active = False
    await record_audit(
        db,
        action="organization.restored",
        user=user,
        module="society_trust",
        entity_type="Organization",
        entity_id=organization.id,
        before=before,
        after={"is_active": False, "archived_at": None},
        request=request,
        target_organization_id=organization.id,
    )
    await db.flush()
    return await _organization_out_for_db(db, organization)


@router.patch("/{organization_id}/license", response_model=OrganizationOut)
async def update_organization_license(
    organization_id: UUID,
    payload: OrganizationLicenseUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_superuser)],
):
    organization = await db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    if organization.archived_at is not None:
        raise HTTPException(
            status_code=409,
            detail="Archived Organization is read-only. Restore it before changing license settings.",
        )
    before = {
        "enabled_modules": list(organization.enabled_modules or []),
        "license_expires_at": organization.license_expires_at.isoformat()
        if organization.license_expires_at
        else None,
    }
    if payload.enabled_modules is not None:
        from app.models.license import ModuleDefinition

        rows = await db.execute(
            select(ModuleDefinition.code).where(
                ModuleDefinition.code.in_(set(payload.enabled_modules))
            )
        )
        valid = set(rows.scalars().all())
        unknown = sorted(set(payload.enabled_modules) - valid)
        if unknown:
            raise HTTPException(status_code=422, detail=f"Unknown modules: {', '.join(unknown)}")
        unavailable = sorted(valid - IMPLEMENTED_MODULES)
        if unavailable:
            raise HTTPException(
                status_code=409, detail=f"Modules not implemented yet: {', '.join(unavailable)}"
            )
        organization.enabled_modules = sorted(valid)
    if payload.license_expires_at is not None:
        if payload.license_expires_at <= datetime.now(UTC):
            raise HTTPException(status_code=422, detail="License expiry must be in the future")
        organization.license_expires_at = payload.license_expires_at
    await record_audit(
        db,
        action="organization.license_updated",
        user=user,
        module="society_trust",
        entity_type="Organization",
        entity_id=organization.id,
        before=before,
        after={
            "enabled_modules": list(organization.enabled_modules or []),
            "license_expires_at": organization.license_expires_at.isoformat()
            if organization.license_expires_at
            else None,
        },
        request=request,
        target_organization_id=organization.id,
    )
    await db.flush()
    return await _organization_out_for_db(db, organization)


@router.get("/{organization_id}/schools", response_model=list[SchoolOut])
async def list_organization_schools(
    organization_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("organization.view"))],
):
    await ensure_organization_access(user, organization_id)
    result = await db.execute(
        select(School)
        .options(selectinload(School.configuration), selectinload(School.udise_codes))
        .where(School.organization_id == organization_id, School.deleted_at.is_(None))
        .order_by(School.created_at)
    )
    return list(result.scalars().all())


@router.get("/{organization_id}/dashboard", response_model=OrganizationDashboardOut)
async def get_organization_dashboard(
    organization_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("organization.view"))],
):
    """Return one consolidated view plus a separate summary for every school unit."""
    await ensure_organization_access(user, organization_id)
    organization = await db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    result = await db.execute(
        select(
            School.id,
            School.code,
            School.udise_code,
            SchoolConfiguration.name,
            School.is_active,
        )
        .join(SchoolConfiguration, SchoolConfiguration.school_id == School.id)
        .where(School.organization_id == organization_id, School.deleted_at.is_(None))
        .group_by(
            School.id,
            School.code,
            School.udise_code,
            SchoolConfiguration.name,
            School.is_active,
        )
        .order_by(SchoolConfiguration.name)
    )
    school_rows = result.all()
    school_ids = [row.id for row in school_rows]
    india_time = timezone(timedelta(hours=5, minutes=30))
    today = datetime.now(india_time).date()
    start_of_day = datetime.combine(today, time.min, tzinfo=india_time).astimezone(UTC)
    end_of_day = start_of_day + timedelta(days=1)

    def integer_map(rows: list[tuple]) -> dict[UUID, int]:
        return {row[0]: int(row[1] or 0) for row in rows}

    student_counts: dict[UUID, int] = {}
    teacher_counts: dict[UUID, int] = {}
    student_attendance: dict[UUID, tuple[int, int]] = {}
    teacher_attendance: dict[UUID, tuple[int, int]] = {}
    collections: dict[UUID, Decimal] = {}
    dues: dict[UUID, tuple[Decimal, Decimal]] = {}
    performance: dict[UUID, tuple[Decimal, int]] = {}

    if school_ids:
        student_counts = integer_map(
            (
                await db.execute(
                    select(Student.school_id, func.count(Student.id))
                    .where(Student.school_id.in_(school_ids), Student.status == "active")
                    .group_by(Student.school_id)
                )
            ).all()
        )
        teacher_counts = integer_map(
            (
                await db.execute(
                    select(Teacher.school_id, func.count(Teacher.id))
                    .where(Teacher.school_id.in_(school_ids), Teacher.is_active.is_(True))
                    .group_by(Teacher.school_id)
                )
            ).all()
        )

        student_attendance_rows = (
            await db.execute(
                select(
                    StudentAttendance.school_id,
                    func.count(StudentAttendance.id),
                    func.sum(case((StudentAttendance.status == "present", 1), else_=0)),
                )
                .where(
                    StudentAttendance.school_id.in_(school_ids),
                    StudentAttendance.attendance_date == today,
                )
                .group_by(StudentAttendance.school_id)
            )
        ).all()
        student_attendance = {
            row[0]: (int(row[2] or 0), int(row[1] or 0)) for row in student_attendance_rows
        }
        teacher_attendance_rows = (
            await db.execute(
                select(
                    TeacherAttendance.school_id,
                    func.count(TeacherAttendance.id),
                    func.sum(case((TeacherAttendance.status == "present", 1), else_=0)),
                )
                .where(
                    TeacherAttendance.school_id.in_(school_ids),
                    TeacherAttendance.attendance_date == today,
                )
                .group_by(TeacherAttendance.school_id)
            )
        ).all()
        teacher_attendance = {
            row[0]: (int(row[2] or 0), int(row[1] or 0)) for row in teacher_attendance_rows
        }

        collection_rows = (
            await db.execute(
                select(Payment.school_id, func.coalesce(func.sum(Payment.amount), 0))
                .where(
                    Payment.school_id.in_(school_ids),
                    Payment.status == "posted",
                    Payment.collected_at >= start_of_day,
                    Payment.collected_at < end_of_day,
                )
                .group_by(Payment.school_id)
            )
        ).all()
        collections = {row[0]: Decimal(str(row[1] or 0)) for row in collection_rows}

        posted_allocations = (
            select(
                PaymentAllocation.charge_id.label("charge_id"),
                func.coalesce(func.sum(PaymentAllocation.amount), 0).label("paid"),
            )
            .join(Payment, Payment.id == PaymentAllocation.payment_id)
            .where(Payment.status == "posted")
            .group_by(PaymentAllocation.charge_id)
            .subquery()
        )
        balance = func.greatest(
            StudentCharge.amount - func.coalesce(posted_allocations.c.paid, 0), 0
        )
        due_rows = (
            await db.execute(
                select(
                    StudentCharge.school_id,
                    func.coalesce(func.sum(balance), 0),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    and_(
                                        StudentCharge.due_date.is_not(None),
                                        StudentCharge.due_date < today,
                                    ),
                                    balance,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                )
                .outerjoin(posted_allocations, posted_allocations.c.charge_id == StudentCharge.id)
                .where(StudentCharge.school_id.in_(school_ids))
                .group_by(StudentCharge.school_id)
            )
        ).all()
        dues = {row[0]: (Decimal(str(row[1] or 0)), Decimal(str(row[2] or 0))) for row in due_rows}

        percentage = StudentMark.marks_obtained / func.nullif(StudentMark.max_marks, 0) * 100
        performance_rows = (
            await db.execute(
                select(StudentMark.school_id, func.avg(percentage), func.count(StudentMark.id))
                .where(
                    StudentMark.school_id.in_(school_ids),
                    StudentMark.is_locked.is_(True),
                    StudentMark.max_marks > 0,
                )
                .group_by(StudentMark.school_id)
            )
        ).all()
        performance = {
            row[0]: (Decimal(str(row[1])), int(row[2]))
            for row in performance_rows
            if row[1] is not None
        }

    def percentage_of(present: int, marked: int) -> float:
        return round((present / marked * 100), 2) if marked else 0

    units: list[OrganizationDashboardUnit] = []
    for row in school_rows:
        student_present, student_marked = student_attendance.get(row.id, (0, 0))
        teacher_present, teacher_marked = teacher_attendance.get(row.id, (0, 0))
        outstanding, overdue = dues.get(row.id, (Decimal("0"), Decimal("0")))
        school_performance = performance.get(row.id)
        units.append(
            OrganizationDashboardUnit(
                school_id=row.id,
                code=row.code,
                udise_code=row.udise_code,
                name=row.name,
                is_active=row.is_active,
                student_count=student_counts.get(row.id, 0),
                teacher_count=teacher_counts.get(row.id, 0),
                today_collection=f"{collections.get(row.id, Decimal('0')):.2f}",
                outstanding_due=f"{outstanding:.2f}",
                overdue_due=f"{overdue:.2f}",
                student_attendance_present=student_present,
                student_attendance_marked=student_marked,
                student_attendance_percentage=percentage_of(student_present, student_marked),
                teacher_attendance_present=teacher_present,
                teacher_attendance_marked=teacher_marked,
                teacher_attendance_percentage=percentage_of(teacher_present, teacher_marked),
                student_performance_percentage=(
                    round(float(school_performance[0]), 2) if school_performance else None
                ),
            )
        )

    total_student_present = sum(unit.student_attendance_present for unit in units)
    total_student_marked = sum(unit.student_attendance_marked for unit in units)
    total_teacher_present = sum(unit.teacher_attendance_present for unit in units)
    total_teacher_marked = sum(unit.teacher_attendance_marked for unit in units)
    total_performance_records = sum(item[1] for item in performance.values())
    organization_performance = (
        sum(item[0] * item[1] for item in performance.values()) / total_performance_records
        if total_performance_records
        else None
    )
    return OrganizationDashboardOut(
        organization_id=organization.id,
        organization_name=organization.name,
        unit_count=len(units),
        active_unit_count=sum(1 for unit in units if unit.is_active),
        allowed_school_count=organization.allowed_schools,
        remaining_school_count=max(organization.allowed_schools - len(units), 0),
        student_count=sum(unit.student_count for unit in units),
        teacher_count=sum(unit.teacher_count for unit in units),
        as_of_date=today,
        today_collection=f"{sum(collections.values(), Decimal('0')):.2f}",
        outstanding_due=f"{sum((item[0] for item in dues.values()), Decimal('0')):.2f}",
        overdue_due=f"{sum((item[1] for item in dues.values()), Decimal('0')):.2f}",
        student_attendance_present=total_student_present,
        student_attendance_marked=total_student_marked,
        student_attendance_percentage=percentage_of(total_student_present, total_student_marked),
        teacher_attendance_present=total_teacher_present,
        teacher_attendance_marked=total_teacher_marked,
        teacher_attendance_percentage=percentage_of(total_teacher_present, total_teacher_marked),
        student_performance_percentage=(
            round(float(organization_performance), 2)
            if organization_performance is not None
            else None
        ),
        units=units,
    )


@router.post(
    "/{organization_id}/academic-years",
    response_model=OrganizationAcademicYearOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization_academic_year(
    organization_id: UUID,
    payload: AcademicYearCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("academic_year.manage"))],
):
    await ensure_organization_access(user, organization_id)
    if payload.ends_on <= payload.starts_on:
        raise HTTPException(
            status_code=422, detail="Academic year end date must be after start date"
        )
    exists = await db.execute(
        select(OrganizationAcademicYear).where(
            OrganizationAcademicYear.organization_id == organization_id,
            OrganizationAcademicYear.code == payload.code,
        )
    )
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Organization academic year already exists")

    organization_year = OrganizationAcademicYear(
        organization_id=organization_id,
        **payload.model_dump(),
    )
    db.add(organization_year)
    await db.flush()

    campus_result = await db.execute(
        select(Campus)
        .join(School, School.id == Campus.school_id)
        .where(School.organization_id == organization_id)
    )
    for campus in campus_result.scalars().all():
        existing_year = await db.execute(
            select(AcademicYear).where(
                AcademicYear.campus_id == campus.id,
                AcademicYear.code == payload.code,
            )
        )
        campus_year = existing_year.scalar_one_or_none()
        if campus_year:
            if campus_year.starts_on != payload.starts_on or campus_year.ends_on != payload.ends_on:
                raise HTTPException(
                    status_code=409,
                    detail=f"Campus {campus.code} already has conflicting academic-year dates",
                )
            campus_year.organization_academic_year_id = organization_year.id
        else:
            db.add(
                AcademicYear(
                    campus_id=campus.id,
                    organization_academic_year_id=organization_year.id,
                    **payload.model_dump(),
                )
            )
    await db.flush()
    await record_audit(
        db,
        action="academic_year.created",
        user=user,
        module="society_trust",
        entity_type="OrganizationAcademicYear",
        entity_id=organization_year.id,
        after={
            "organization_id": str(organization_id),
            "code": organization_year.code,
            "starts_on": organization_year.starts_on.isoformat(),
            "ends_on": organization_year.ends_on.isoformat(),
        },
        request=request,
    )
    return organization_year


@router.patch(
    "/academic-years/{academic_year_id}",
    response_model=OrganizationAcademicYearOut,
)
async def update_organization_academic_year(
    academic_year_id: UUID,
    payload: AcademicYearUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("academic_year.manage"))],
):
    year = await db.get(OrganizationAcademicYear, academic_year_id)
    if not year:
        raise HTTPException(status_code=404, detail="Organization academic year not found")
    await ensure_organization_access(user, year.organization_id)
    if not user.is_superuser and "ORGANIZATION_ADMIN" not in get_role_codes(user):
        raise HTTPException(
            status_code=403, detail="Only Organization Admin or Super Admin can edit academic years"
        )

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return year
    before = {
        "code": year.code,
        "name": year.name,
        "starts_on": year.starts_on.isoformat(),
        "ends_on": year.ends_on.isoformat(),
        "notes": year.notes,
        "status": year.status,
    }

    # Once activated/closed, keep the calendar identity and date boundary immutable.
    # Name/notes remain editable for harmless corrections.
    protected_changes = {
        field
        for field in ("code", "starts_on", "ends_on")
        if field in changes and changes[field] != getattr(year, field)
    }
    if year.status != "draft" and protected_changes:
        raise HTTPException(
            status_code=409,
            detail="Active or historical academic-year code/dates cannot be changed; only name and notes may be edited",
        )

    new_start = changes.get("starts_on", year.starts_on)
    new_end = changes.get("ends_on", year.ends_on)
    if new_end <= new_start:
        raise HTTPException(
            status_code=422, detail="Academic year end date must be after start date"
        )

    if "code" in changes and changes["code"] != year.code:
        duplicate = await db.execute(
            select(OrganizationAcademicYear.id).where(
                OrganizationAcademicYear.organization_id == year.organization_id,
                OrganizationAcademicYear.code == changes["code"],
                OrganizationAcademicYear.id != year.id,
            )
        )
        if duplicate.scalar_one_or_none():
            raise HTTPException(
                status_code=409, detail="Organization academic year code already exists"
            )

    for field, value in changes.items():
        setattr(year, field, value)

    campus_years = await db.execute(
        select(AcademicYear).where(AcademicYear.organization_academic_year_id == year.id)
    )
    for campus_year in campus_years.scalars().all():
        campus_year.code = year.code
        campus_year.name = year.name
        campus_year.starts_on = year.starts_on
        campus_year.ends_on = year.ends_on
        campus_year.notes = year.notes

    await db.flush()
    await record_audit(
        db,
        action="academic_year.updated",
        user=user,
        module="society_trust",
        entity_type="OrganizationAcademicYear",
        entity_id=year.id,
        before=before,
        after={
            "code": year.code,
            "name": year.name,
            "starts_on": year.starts_on.isoformat(),
            "ends_on": year.ends_on.isoformat(),
            "notes": year.notes,
            "status": year.status,
        },
        request=request,
    )
    return year


@router.get(
    "/{organization_id}/academic-years",
    response_model=list[OrganizationAcademicYearOut],
)
async def list_organization_academic_years(
    organization_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("academic_year.view"))],
):
    await ensure_organization_read_access(user, organization_id)
    result = await db.execute(
        select(OrganizationAcademicYear)
        .where(OrganizationAcademicYear.organization_id == organization_id)
        .order_by(OrganizationAcademicYear.starts_on.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/academic-years/{academic_year_id}/activate",
    response_model=OrganizationAcademicYearOut,
)
async def activate_organization_academic_year(
    academic_year_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("academic_year.manage"))],
):
    year = await db.get(OrganizationAcademicYear, academic_year_id)
    if not year:
        raise HTTPException(status_code=404, detail="Organization academic year not found")
    await ensure_organization_access(user, year.organization_id)

    active_result = await db.execute(
        select(OrganizationAcademicYear).where(
            OrganizationAcademicYear.organization_id == year.organization_id,
            OrganizationAcademicYear.id != year.id,
            OrganizationAcademicYear.status == "active",
        )
    )
    for previous in active_result.scalars().all():
        previous.status = "closed"
        previous.is_read_only = True

    campus_years = await db.execute(
        select(AcademicYear).where(AcademicYear.organization_academic_year_id == year.id)
    )
    for campus_year in campus_years.scalars().all():
        other_active = await db.execute(
            select(AcademicYear).where(
                AcademicYear.campus_id == campus_year.campus_id,
                AcademicYear.id != campus_year.id,
                AcademicYear.status == "active",
            )
        )
        for previous in other_active.scalars().all():
            previous.status = "closed"
            previous.is_read_only = True
        campus_year.status = "active"
        campus_year.is_read_only = False
        campus_year.activated_at = datetime.now(UTC)
        campus_year.activated_by = user.id

    year.status = "active"
    year.is_read_only = False
    year.activated_at = datetime.now(UTC)
    year.activated_by = user.id
    await db.flush()
    await record_audit(
        db,
        action="academic_year.activated",
        user=user,
        module="society_trust",
        entity_type="OrganizationAcademicYear",
        entity_id=year.id,
        after={"organization_id": str(year.organization_id), "code": year.code},
        request=request,
    )
    return year
