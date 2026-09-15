import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.deps import (
    ensure_school_access,
    get_current_active_superuser,
    get_current_user,
    require_permissions,
)
from app.core.erp_codes import (
    area_short_code,
    format_school_code,
    school_prefix,
)
from app.db.session import get_db
from app.models.governance import SchoolCodeRegistry
from app.models.license import SchoolLicense
from app.models.organization import AcademicYear, Campus, Organization, OrganizationAcademicYear
from app.models.school import School, SchoolConfiguration, SchoolUDISECode
from app.models.subscription import OrganizationSubscription, SchoolSubscription, SubscriptionPlan
from app.models.user import User
from app.schemas.license import SchoolLicenseOut, SchoolLicenseUpdate
from app.schemas.school import (
    SchoolConfigurationOut,
    SchoolConfigurationUpdate,
    SchoolCreate,
    SchoolOut,
    SchoolProfileUpdate,
    SchoolLifecycleAction,
    SchoolUpdate,
    UDISECodeInput,
)
from app.services.audit import record_audit
from app.services.backups import has_recent_successful_backup
from app.services.corrections import consume_annual_correction
from app.services.licensing import (
    IMPLEMENTED_MODULES,
    PHASE1_MODULES,
    next_may_31,
)
from app.services.session_control import revoke_school_sessions
from app.services.subscriptions import attach_school_entitlement, effective_modules, plan_for_school

router = APIRouter(prefix="/schools", tags=["Schools"])


def _generate_license_key() -> str:
    return f"SERP-{secrets.token_hex(16).upper()}"


async def _school_code_from_input(
    db: AsyncSession, *, school_name: str, area_name: str
) -> tuple[str, str]:
    """Generate the permanent human-readable ERP School code.

    Codes use the approved <school-prefix>-<area-code>-<sequence> format.
    SchoolCodeRegistry is append-only, so archived School codes are never reused.
    The Organization row is already locked by the caller, serializing School
    creation within an Organization while the registry unique constraint is the
    final cross-request safety net.
    """
    school_part = school_prefix(school_name)
    village_part = area_short_code(area_name)
    prefix = f"{school_part}-{village_part}-"
    issued = (
        await db.execute(
            select(SchoolCodeRegistry.code).where(SchoolCodeRegistry.code.like(f"{prefix}%"))
        )
    ).scalars().all()
    sequences = []
    for issued_code in issued:
        suffix = issued_code.removeprefix(prefix)
        if suffix.isdigit():
            sequences.append(int(suffix))
    code = format_school_code(school_part, village_part, max(sequences, default=0) + 1)
    return code, village_part


async def _load_school(
    db: AsyncSession, school_id: UUID, *, include_deleted: bool = False
) -> School | None:
    query = (
        select(School)
        .options(selectinload(School.configuration), selectinload(School.udise_codes))
        .where(School.id == school_id)
    )
    if not include_deleted:
        query = query.where(School.deleted_at.is_(None))
    result = await db.execute(query)
    return result.scalar_one_or_none()


def _require_reloaded_school(school: School | None) -> School:
    if school is None:
        raise HTTPException(status_code=500, detail="School could not be reloaded after update")
    return school


async def _lock_and_check_school_capacity(
    db: AsyncSession, organization_id: UUID, *, adding_slot: bool
) -> tuple[Organization, OrganizationSubscription | None, int, int]:
    """Serialize capacity-sensitive School lifecycle operations per Organization.

    Non-archived School records consume capacity, including disabled and
    pending-activation Schools. Restoring an archived School consumes one new
    slot; enabling an existing non-archived School does not.
    """
    organization = (
        await db.execute(
            select(Organization)
            .where(Organization.id == organization_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    subscription = (
        await db.execute(
            select(OrganizationSubscription)
            .where(
                OrganizationSubscription.organization_id == organization.id,
                OrganizationSubscription.status.in_(["trial", "pending_payment", "active", "overdue"]),
            )
            .order_by(OrganizationSubscription.created_at.desc())
            .limit(1)
            .with_for_update()
        )
    ).scalar_one_or_none()
    count = int(
        (
            await db.execute(
                select(func.count(School.id)).where(
                    School.organization_id == organization.id,
                    School.deleted_at.is_(None),
                )
            )
        ).scalar_one()
        or 0
    )
    limit = (
        1
        if subscription and subscription.billing_cycle == "trial"
        else (subscription.school_count if subscription else organization.allowed_schools)
    )
    projected = count + (1 if adding_slot else 0)
    if projected > limit:
        raise HTTPException(
            status_code=409,
            detail=f"Organization School limit reached ({limit}). Increase the subscription capacity before this action.",
        )
    return organization, subscription, count, limit


async def _validate_udise_codes(
    db: AsyncSession, values: list[UDISECodeInput], *, current_school_id: UUID | None = None
) -> list[UDISECodeInput]:
    cleaned: list[UDISECodeInput] = []
    seen: set[str] = set()
    for item in values:
        code = item.udise_code.strip()
        if not code or code in seen:
            continue
        seen.add(code)
        cleaned.append(
            UDISECodeInput(udise_code=code, label=item.label, is_primary=item.is_primary)
        )
    if cleaned and not any(item.is_primary for item in cleaned):
        cleaned[0].is_primary = True
    for item in cleaned:
        query = select(SchoolUDISECode).where(
            SchoolUDISECode.udise_code == item.udise_code,
            SchoolUDISECode.is_active.is_(True),
            SchoolUDISECode.deleted_at.is_(None),
        )
        if current_school_id:
            query = query.where(SchoolUDISECode.school_id != current_school_id)
        existing = (await db.execute(query)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"UDISE code {item.udise_code} is already assigned to another active School",
            )
    return cleaned


async def _replace_udise_codes(
    db: AsyncSession, school: School, values: list[UDISECodeInput]
) -> None:
    values = await _validate_udise_codes(db, values, current_school_id=school.id)
    now = datetime.now(UTC)
    result = await db.execute(select(SchoolUDISECode).where(SchoolUDISECode.school_id == school.id))
    existing = list(result.scalars().all())
    by_code = {row.udise_code: row for row in existing}
    requested = {item.udise_code for item in values}
    for row in existing:
        if row.udise_code not in requested and row.deleted_at is None:
            row.is_active = False
            row.deleted_at = now
            row.is_primary = False
    for item in values:
        row = by_code.get(item.udise_code)
        if row:
            row.label = item.label
            row.is_primary = item.is_primary
            row.is_active = True
            row.deleted_at = None
        else:
            db.add(
                SchoolUDISECode(
                    school_id=school.id,
                    udise_code=item.udise_code,
                    label=item.label,
                    is_primary=item.is_primary,
                    is_active=True,
                )
            )
    primary = next((item.udise_code for item in values if item.is_primary), None)
    school.udise_code = primary
    await db.flush()


@router.post("", response_model=SchoolOut, status_code=status.HTTP_201_CREATED)
async def create_school(
    payload: SchoolCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(get_current_active_superuser)],
):
    # Serialize School creation per Organization so concurrent requests cannot
    # over-allocate the final purchased School slot.
    organization, subscription, _active_count, _school_limit = await _lock_and_check_school_capacity(
        db, payload.organization_id, adding_slot=True
    )
    if organization.archived_at is not None:
        raise HTTPException(
            status_code=409, detail="Cannot create a School under an archived Organization"
        )
    if not organization.is_active:
        raise HTTPException(
            status_code=409, detail="Cannot create a School under a disabled Organization"
        )
    # V1.1.24.01: plan authority is School-level. The Organization plan is only a legacy/default fallback.
    selected_plan_id = payload.subscription_plan_id or (subscription.plan_id if subscription else None)
    plan = await db.get(SubscriptionPlan, selected_plan_id) if selected_plan_id else None
    if payload.subscription_plan_id and (not plan or not plan.is_active):
        raise HTTPException(status_code=404, detail="Active School subscription plan not found")
    if subscription and subscription.expires_at <= datetime.now(UTC):
        raise HTTPException(
            status_code=409,
            detail="Organization subscription has expired. Renew or convert it before adding a School.",
        )


    code, generated_area_code = await _school_code_from_input(
        db,
        school_name=payload.configuration.name,
        area_name=payload.configuration.area,
    )
    # ERP code may never be reused, including archived historical rows. Reserve it
    # in the permanent registry before the School is created. The unique registry
    # constraint also protects against concurrent creation races.
    duplicate_code = await db.execute(
        select(SchoolCodeRegistry.id).where(SchoolCodeRegistry.code == code)
    )
    if duplicate_code.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Generated ERP School Code was already issued; refresh and try again",
        )
    registry = SchoolCodeRegistry(organization_id=organization.id, code=code)
    db.add(registry)
    await db.flush()

    udise_values = await _validate_udise_codes(db, payload.udise_codes)
    primary_udise = next((item.udise_code for item in udise_values if item.is_primary), None)
    trial_access = bool(subscription and subscription.billing_cycle == "trial")
    # Trial is immediately operational under its restricted entitlement. Paid
    # Schools remain disabled until the Organization Admin completes ERP
    # activation. Plan assignment alone must never unlock modules or users.
    paid_pending_activation = bool(not trial_access)
    school = School(
        code=code,
        udise_code=primary_udise,
        organization_id=organization.id,
        is_active=not paid_pending_activation,
    )
    db.add(school)
    await db.flush()
    registry.issued_school_id = school.id

    config_data = payload.configuration.model_dump()
    config_data["area_code"] = generated_area_code
    config = SchoolConfiguration(school_id=school.id, **config_data)
    db.add(config)
    for item in udise_values:
        db.add(
            SchoolUDISECode(
                school_id=school.id,
                udise_code=item.udise_code,
                label=item.label,
                is_primary=item.is_primary,
                is_active=False,
            )
        )

    now = datetime.now(UTC)
    requested_modules = (
        effective_modules(plan, trial=trial_access)
        if subscription and plan
        else (payload.enabled_modules or list(PHASE1_MODULES))
    )
    unavailable = sorted(set(requested_modules) - IMPLEMENTED_MODULES)
    if unavailable:
        raise HTTPException(
            status_code=409, detail=f"Modules not implemented yet: {', '.join(unavailable)}"
        )
    # Subscription-backed schools use the exact module entitlement attached
    # to their selected Plan. There is no mandatory/Core ERP module bundle.
    if organization.enabled_modules:
        invalid = sorted(set(requested_modules) - set(organization.enabled_modules))
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"Modules not enabled for Organization: {', '.join(invalid)}",
            )
    expiry = (
        subscription.expires_at
        if subscription
        else (payload.license_expires_at or organization.license_expires_at or next_may_31(now))
    )
    if subscription and plan:
        try:
            await attach_school_entitlement(
                db,
                account=subscription,
                plan=plan,
                school_id=school.id,
                created_by=actor.id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    else:
        db.add(
            SchoolLicense(
                school_id=school.id,
                license_key=_generate_license_key(),
                enabled_modules=requested_modules,
                max_users=payload.max_users,
                starts_at=now,
                expires_at=expiry,
                is_active=True,
            )
        )

    # MAIN is an internal compatibility scope. The School/Branch itself is the visible unit.
    main_campus = Campus(
        school_id=school.id,
        code="MAIN",
        name=payload.configuration.short_name or payload.configuration.name,
        city=payload.configuration.city or payload.configuration.area,
        state=payload.configuration.state,
        country=payload.configuration.country,
        enabled_modules=list(requested_modules),
        license_starts_at=now,
        license_expires_at=expiry,
    )
    db.add(main_campus)
    await db.flush()


    # If the Organization already has Academic Years, create the internal School
    # projections now. Academic Years remain user-managed only at Organization level.
    org_years = await db.execute(
        select(OrganizationAcademicYear).where(
            OrganizationAcademicYear.organization_id == organization.id
        )
    )
    for org_year in org_years.scalars().all():
        db.add(
            AcademicYear(
                campus_id=main_campus.id,
                organization_academic_year_id=org_year.id,
                code=org_year.code,
                name=org_year.name,
                starts_on=org_year.starts_on,
                ends_on=org_year.ends_on,
                status=org_year.status,
                is_read_only=org_year.is_read_only,
                activated_at=org_year.activated_at,
                activated_by=org_year.activated_by,
                notes=org_year.notes,
            )
        )
    await db.flush()
    await record_audit(
        db,
        action="school.created",
        user=actor,
        module="school_admin",
        entity_type="School",
        entity_id=school.id,
        after={
            "code": school.code,
            "name": config.name,
            "area": config.area,
            "area_code": config.area_code,
            "udise_codes": [u.udise_code for u in udise_values],
            "subscription_id": str(subscription.id) if subscription else None,
            "activation_status": "not_required" if trial_access else ("pending" if subscription else "subscription_pending"),
        },
        request=request,
        target_organization_id=organization.id,
        target_school_id=school.id,
    )
    return _require_reloaded_school(await _load_school(db, school.id))


@router.get("", response_model=list[SchoolOut])
async def list_schools(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = 0,
    limit: int = 100,
    include_archived: bool = False,
):
    query = select(School).options(
        selectinload(School.configuration), selectinload(School.udise_codes)
    )
    if include_archived and not (
        current_user.is_superuser or current_user.account_type == "ORGANIZATION_ADMIN"
    ):
        raise HTTPException(
            status_code=403,
            detail="Archived School access is limited to Organization Admin or Super Admin",
        )
    if not include_archived:
        query = query.where(School.deleted_at.is_(None))
    if current_user.is_superuser:
        query = query.order_by(School.created_at.desc()).offset(skip).limit(limit)
    elif current_user.account_type == "ORGANIZATION_ADMIN" and current_user.organization_id:
        query = query.where(School.organization_id == current_user.organization_id).order_by(
            School.created_at.desc()
        )
    elif current_user.school_id:
        query = query.where(School.id == current_user.school_id, School.deleted_at.is_(None))
    else:
        return []
    result = await db.execute(query)
    return list(result.scalars().unique().all())


@router.get("/{school_id}", response_model=SchoolOut)
async def get_school(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("school.config.view"))],
):
    await ensure_school_access(current_user, db, school_id)
    school = await _load_school(db, school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    return school


@router.patch("/{school_id}/status", response_model=SchoolOut)
async def set_school_status(
    school_id: UUID,
    payload: SchoolUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_superuser)],
):
    school = await db.get(School, school_id)
    if not school or school.deleted_at is not None:
        raise HTTPException(status_code=404, detail="School not found")
    if payload.is_active is None:
        raise HTTPException(status_code=422, detail="is_active is required")
    reason = (payload.reason or "").strip()
    if len(reason) < 3:
        raise HTTPException(status_code=422, detail="Reason is required")
    if payload.is_active and school.organization_id:
        organization, _subscription, _count, _limit = await _lock_and_check_school_capacity(
            db, school.organization_id, adding_slot=False
        )
        if organization.archived_at is not None:
            raise HTTPException(
                status_code=409,
                detail="Organization is archived. Restore it before enabling this School.",
            )
        if not organization.is_active:
            raise HTTPException(
                status_code=409,
                detail="Organization is disabled. Please activate the Organization before enabling this School.",
            )
        entitlement = (
            await db.execute(
                select(SchoolSubscription)
                .where(SchoolSubscription.school_id == school.id)
                .order_by(SchoolSubscription.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if entitlement:
            account = await db.get(
                OrganizationSubscription, entitlement.organization_subscription_id
            )
            if account and account.billing_cycle != "trial" and entitlement.status != "active":
                raise HTTPException(
                    status_code=409,
                    detail="School ERP activation is pending. Complete Organization Admin activation before enabling the School.",
                )
    before = {"is_active": school.is_active}
    school.is_active = payload.is_active
    if not school.is_active:
        await revoke_school_sessions(db, school.id)
    await record_audit(
        db,
        action="school.enabled" if school.is_active else "school.disabled",
        user=user,
        module="school_admin",
        entity_type="School",
        entity_id=school.id,
        before=before,
        after={"is_active": school.is_active},
        metadata={"reason": reason},
        request=request,
        target_organization_id=school.organization_id,
        target_school_id=school.id,
    )
    await db.flush()
    return _require_reloaded_school(await _load_school(db, school.id))


@router.post("/{school_id}/archive", response_model=SchoolOut)
async def archive_school(
    school_id: UUID,
    payload: SchoolLifecycleAction,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_superuser)],
):
    school = await db.get(School, school_id)
    if not school or school.deleted_at is not None:
        raise HTTPException(status_code=404, detail="School not found")
    if school.is_active:
        raise HTTPException(status_code=409, detail="Disable the School before archiving it")
    archive_settings = get_settings()
    if archive_settings.require_recent_backup_for_archive and not has_recent_successful_backup(
        archive_settings.archive_backup_max_age_hours
    ):
        raise HTTPException(
            status_code=409,
            detail=f"A successful database backup from the last {archive_settings.archive_backup_max_age_hours} hours is required before archiving a School.",
        )
    now = datetime.now(UTC)
    school.deleted_at = now
    school.deleted_by = user.id
    school.is_active = False
    revoked = await revoke_school_sessions(db, school.id, "school_archived")
    # UDISE is a government/business identifier that may legitimately be assigned
    # to a replacement School after archive. Preserve history but release active uniqueness.
    await db.execute(
        update(SchoolUDISECode)
        .where(SchoolUDISECode.school_id == school.id, SchoolUDISECode.deleted_at.is_(None))
        .values(is_active=False, deleted_at=now, is_primary=False)
    )
    await record_audit(
        db,
        action="school.archived",
        user=user,
        module="school_admin",
        entity_type="School",
        entity_id=school.id,
        before={"is_active": False, "archived_at": None, "code": school.code},
        after={"is_active": False, "archived_at": now.isoformat(), "code": school.code},
        metadata={"sessions_revoked": revoked, "reason": payload.reason.strip()},
        request=request,
        target_organization_id=school.organization_id,
        target_school_id=school.id,
    )
    await db.flush()
    return _require_reloaded_school(await _load_school(db, school.id, include_deleted=True))


@router.post("/{school_id}/restore", response_model=SchoolOut)
async def restore_school(
    school_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_superuser)],
):
    school = await _load_school(db, school_id, include_deleted=True)
    if not school or school.deleted_at is None:
        raise HTTPException(status_code=404, detail="Archived School not found")
    organization, _subscription, _count, _limit = await _lock_and_check_school_capacity(
        db, school.organization_id, adding_slot=True
    )
    if organization.archived_at is not None:
        raise HTTPException(
            status_code=409, detail="Restore the Organization before restoring this School"
        )
    before = {"archived_at": school.deleted_at.isoformat(), "is_active": school.is_active}
    school.deleted_at = None
    school.deleted_by = None
    # Restored Schools remain disabled until an administrator explicitly enables
    # them. Restore historical UDISE identifiers only when they have not been
    # reassigned to another active School in the meantime.
    school.is_active = False
    restored_udise = 0
    skipped_udise = 0
    udise_rows = (
        (await db.execute(select(SchoolUDISECode).where(SchoolUDISECode.school_id == school.id)))
        .scalars()
        .all()
    )
    restored_rows: list[SchoolUDISECode] = []
    for row in udise_rows:
        conflict = (
            await db.execute(
                select(SchoolUDISECode.id).where(
                    SchoolUDISECode.udise_code == row.udise_code,
                    SchoolUDISECode.school_id != school.id,
                    SchoolUDISECode.is_active.is_(True),
                    SchoolUDISECode.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if conflict:
            row.is_active = False
            row.deleted_at = row.deleted_at or datetime.now(UTC)
            row.is_primary = False
            skipped_udise += 1
            continue
        row.deleted_at = None
        row.is_active = True
        row.is_primary = False
        restored_rows.append(row)
        restored_udise += 1
    # Reconcile the legacy School.udise_code cache with the authoritative rows.
    preferred = next((r for r in restored_rows if r.udise_code == school.udise_code), None)
    primary_row = preferred or (restored_rows[0] if restored_rows else None)
    if primary_row:
        primary_row.is_primary = True
        school.udise_code = primary_row.udise_code
    else:
        school.udise_code = None
    await record_audit(
        db,
        action="school.restored",
        user=user,
        module="school_admin",
        entity_type="School",
        entity_id=school.id,
        before=before,
        after={"archived_at": None, "is_active": False, "code": school.code},
        metadata={"udise_restored": restored_udise, "udise_skipped_conflict": skipped_udise},
        request=request,
        target_organization_id=school.organization_id,
        target_school_id=school.id,
    )
    await db.flush()
    return _require_reloaded_school(await _load_school(db, school.id))


@router.delete("/{school_id}", status_code=status.HTTP_204_NO_CONTENT, deprecated=True)
async def legacy_archive_school(
    school_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("school.admin.edit"))],
):
    # Backward-compatible alias. No physical deletion is performed.
    raise HTTPException(status_code=410, detail="Use the School archive action with a mandatory reason")


@router.patch("/{school_id}/license", response_model=SchoolLicenseOut)
async def update_school_license(
    school_id: UUID,
    payload: SchoolLicenseUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_superuser)],
):
    school = await db.get(School, school_id)
    if not school or school.deleted_at is not None:
        raise HTTPException(status_code=404, detail="School not found")
    result = await db.execute(select(SchoolLicense).where(SchoolLicense.school_id == school_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    organization = (
        await db.get(Organization, school.organization_id) if school.organization_id else None
    )
    before = {
        "enabled_modules": list(lic.enabled_modules or []),
        "expires_at": lic.expires_at.isoformat(),
        "is_active": lic.is_active,
        "max_users": lic.max_users,
    }
    if payload.enabled_modules is not None:
        unavailable = sorted(set(payload.enabled_modules) - IMPLEMENTED_MODULES)
        if unavailable:
            raise HTTPException(
                status_code=409, detail=f"Modules not implemented yet: {', '.join(unavailable)}"
            )
        plan = await plan_for_school(db, school_id)
        if plan:
            account = (await db.execute(
                select(OrganizationSubscription)
                .join(SchoolSubscription, SchoolSubscription.organization_subscription_id == OrganizationSubscription.id)
                .where(SchoolSubscription.school_id == school_id)
                .order_by(SchoolSubscription.created_at.desc())
                .limit(1)
            )).scalar_one_or_none()
            expected = set(effective_modules(plan, trial=bool(account and account.billing_cycle == "trial"))) & IMPLEMENTED_MODULES
            requested = set(payload.enabled_modules)
            if requested != expected:
                missing = sorted(expected - requested)
                extra = sorted(requested - expected)
                parts = []
                if missing:
                    parts.append(f"missing plan modules: {', '.join(missing)}")
                if extra:
                    parts.append(f"modules outside plan: {', '.join(extra)}")
                raise HTTPException(status_code=409, detail="School modules must exactly match the assigned plan (" + "; ".join(parts) + ")")
            lic.enabled_modules = sorted(expected)
        else:
            allowed = set(organization.enabled_modules or []) if organization else set(payload.enabled_modules)
            invalid = sorted(set(payload.enabled_modules) - allowed)
            if invalid:
                raise HTTPException(status_code=422, detail=f"Modules not enabled for Organization: {', '.join(invalid)}")
            lic.enabled_modules = sorted(set(payload.enabled_modules))
    if payload.max_users is not None:
        lic.max_users = payload.max_users
    if payload.expires_at is not None:
        if payload.expires_at <= datetime.now(UTC):
            raise HTTPException(status_code=422, detail="License expiry must be in the future")
        if (
            organization
            and organization.license_expires_at
            and payload.expires_at > organization.license_expires_at
        ):
            raise HTTPException(
                status_code=422, detail="School license cannot exceed Organization license expiry"
            )
        lic.expires_at = payload.expires_at
    if payload.is_active is not None:
        if payload.is_active:
            entitlement = (
                await db.execute(
                    select(SchoolSubscription)
                    .where(SchoolSubscription.school_id == school.id)
                    .order_by(SchoolSubscription.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if entitlement:
                account = await db.get(
                    OrganizationSubscription, entitlement.organization_subscription_id
                )
                if account and account.billing_cycle != "trial" and entitlement.status != "active":
                    raise HTTPException(
                        status_code=409,
                        detail="Paid School license cannot be enabled before Organization Admin ERP activation",
                    )
        lic.is_active = payload.is_active
        if not lic.is_active:
            await revoke_school_sessions(db, school.id, "school_license_disabled")
    if payload.notes is not None:
        lic.notes = payload.notes
    await record_audit(
        db,
        action="school.license_updated",
        user=user,
        module="school_admin",
        entity_type="SchoolLicense",
        entity_id=lic.id,
        before=before,
        after={
            "enabled_modules": list(lic.enabled_modules or []),
            "expires_at": lic.expires_at.isoformat(),
            "is_active": lic.is_active,
            "max_users": lic.max_users,
        },
        request=request,
        target_organization_id=school.organization_id,
        target_school_id=school.id,
    )
    await db.flush()
    data = {c.name: getattr(lic, c.name) for c in lic.__table__.columns}
    data["is_valid"] = lic.is_valid()
    return SchoolLicenseOut(**data)



@router.post("/{school_id}/logo", response_model=SchoolOut)
async def upload_school_logo(
    school_id: UUID,
    file: Annotated[UploadFile, File()],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("school.config.edit"))],
):
    school = await ensure_school_access(current_user, db, school_id)
    if (
        current_user.account_type not in {"SUPER_ADMIN", "ORGANIZATION_ADMIN", "SCHOOL_ADMIN"}
        and not current_user.is_superuser
    ):
        raise HTTPException(status_code=403, detail="School logo upload access denied")
    allowed = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
    content_type = (file.content_type or "").lower()
    if content_type not in allowed:
        raise HTTPException(status_code=422, detail="Logo must be PNG, JPG or WEBP")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Logo file is empty")
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Logo file must be 2 MB or smaller")
    upload_root = Path(get_settings().upload_dir) / "logos" / str(school.id)
    upload_root.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{allowed[content_type]}"
    path = upload_root / filename
    path.write_bytes(data)
    logo_url = f"/uploads/logos/{school.id}/{filename}"
    config = (await db.execute(select(SchoolConfiguration).where(SchoolConfiguration.school_id == school.id))).scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="School profile not found")
    before = {"logo_url": config.logo_url}
    config.logo_url = logo_url
    await record_audit(
        db,
        action="school.logo.uploaded",
        user=current_user,
        module="school_admin",
        entity_type="School",
        entity_id=school.id,
        before=before,
        after={"logo_url": logo_url, "content_type": content_type},
        request=request,
        target_organization_id=school.organization_id,
        target_school_id=school.id,
    )
    await db.flush()
    return _require_reloaded_school(await _load_school(db, school.id))

@router.patch("/{school_id}/profile", response_model=SchoolOut)
async def update_school_profile(
    school_id: UUID,
    payload: SchoolProfileUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("school.config.edit"))],
):
    school = await ensure_school_access(current_user, db, school_id)
    if (
        current_user.account_type not in {"SUPER_ADMIN", "ORGANIZATION_ADMIN", "SCHOOL_ADMIN"}
        and not current_user.is_superuser
    ):
        raise HTTPException(status_code=403, detail="School profile edit access denied")
    if not current_user.is_superuser:
        if not school.organization_id:
            raise HTTPException(status_code=409, detail="School is not assigned to an Organization")
        await consume_annual_correction(
            db,
            request,
            current_user,
            organization_id=school.organization_id,
            school_id=school.id,
            entity_type="school",
            entity_id=school.id,
        )
    config_result = await db.execute(
        select(SchoolConfiguration).where(SchoolConfiguration.school_id == school.id)
    )
    config = config_result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="School profile not found")
    changes = payload.configuration.model_dump(exclude_unset=True)
    # School identity is immutable through normal Edit School.
    identity_fields = {"name", "short_name", "area", "area_code"}
    changed_identity = [field for field in identity_fields if field in changes and changes[field] != getattr(config, field)]
    if changed_identity:
        raise HTTPException(status_code=409, detail="School identity fields are locked after creation")
    required_fields = {"board", "email", "phone", "address_line1", "city", "district", "state", "pincode"}
    for field in required_fields:
        value = changes.get(field, getattr(config, field, None))
        if value is None or (isinstance(value, str) and not value.strip()):
            raise HTTPException(status_code=422, detail=f"{field.replace('_', ' ').title()} is required")
    pincode = str(changes.get("pincode", config.pincode) or "")
    if not (len(pincode) == 6 and pincode.isdigit()):
        raise HTTPException(status_code=422, detail="PIN Code must be exactly 6 digits")
    if changes.get("board", config.board) not in {"State Board", "CBSE", "ICSE"}:
        raise HTTPException(status_code=422, detail="Board/Curriculum must be State Board, CBSE or ICSE")
    before = {field: getattr(config, field) for field in changes}
    for field, value in changes.items():
        setattr(config, field, value)
    # Never touch the lazy relationship from an AsyncSession request handler.
    # Load the current UDISE values explicitly so SQLAlchemy does not attempt
    # synchronous lazy I/O (MissingGreenlet) during a profile update.
    before_udise_result = await db.execute(
        select(SchoolUDISECode.udise_code).where(
            SchoolUDISECode.school_id == school.id,
            SchoolUDISECode.is_active.is_(True),
            SchoolUDISECode.deleted_at.is_(None),
        )
    )
    before_udise = list(before_udise_result.scalars().all())
    if payload.udise_codes is not None:
        if not current_user.is_superuser:
            requested_udise = sorted(
                item.udise_code.strip() for item in payload.udise_codes if item.udise_code.strip()
            )
            if requested_udise != sorted(before_udise):
                raise HTTPException(
                    status_code=403,
                    detail="UDISE identifiers are governed by Platform Owner and cannot be changed by School/Organization Admin",
                )
        else:
            await _replace_udise_codes(db, school, payload.udise_codes)
    await db.flush()
    after_udise_result = await db.execute(
        select(SchoolUDISECode.udise_code).where(
            SchoolUDISECode.school_id == school.id,
            SchoolUDISECode.is_active.is_(True),
            SchoolUDISECode.deleted_at.is_(None),
        )
    )
    after_udise = list(after_udise_result.scalars().all())
    await record_audit(
        db,
        action="school.profile.updated",
        user=current_user,
        module="school_admin",
        entity_type="School",
        entity_id=school.id,
        before={"configuration": before, "udise_codes": before_udise},
        after={"configuration": changes, "udise_codes": after_udise},
        request=request,
        target_organization_id=school.organization_id,
        target_school_id=school.id,
    )
    return _require_reloaded_school(await _load_school(db, school.id))


@router.patch("/{school_id}/configuration", response_model=SchoolConfigurationOut)
async def update_school_configuration(
    school_id: UUID,
    payload: SchoolConfigurationUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("school.config.edit"))],
):
    """Compatibility route; the UI now uses the unified School profile."""
    school = await ensure_school_access(current_user, db, school_id)
    if (
        current_user.account_type not in {"ORGANIZATION_ADMIN", "SCHOOL_ADMIN"}
        and not current_user.is_superuser
    ):
        raise HTTPException(
            status_code=403,
            detail="Only Organization Admin, School Admin or Super Admin can edit the School profile",
        )
    if not current_user.is_superuser:
        if not school.organization_id:
            raise HTTPException(status_code=409, detail="School is not assigned to an Organization")
        await consume_annual_correction(
            db,
            request,
            current_user,
            organization_id=school.organization_id,
            school_id=school.id,
            entity_type="school",
            entity_id=school.id,
        )
    result = await db.execute(
        select(SchoolConfiguration).where(SchoolConfiguration.school_id == school_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="School profile not found")
    update_data = payload.model_dump(exclude_unset=True)
    identity_fields = {"name", "short_name", "area", "area_code"}
    if any(field in update_data and update_data[field] != getattr(config, field) for field in identity_fields):
        raise HTTPException(status_code=409, detail="School identity fields are locked after creation")
    required_fields = {"board", "email", "phone", "address_line1", "city", "district", "state", "pincode"}
    for field in required_fields:
        value = update_data.get(field, getattr(config, field, None))
        if value is None or (isinstance(value, str) and not value.strip()):
            raise HTTPException(status_code=422, detail=f"{field.replace('_', ' ').title()} is required")
    before = {field: getattr(config, field) for field in update_data}
    for field, value in update_data.items():
        setattr(config, field, value)
    await db.flush()
    await record_audit(
        db,
        action="school.profile.updated",
        user=current_user,
        module="school_admin",
        entity_type="SchoolConfiguration",
        entity_id=config.id,
        before=before,
        after=update_data,
        request=request,
        target_organization_id=school.organization_id,
        target_school_id=school_id,
    )
    await db.refresh(config)
    return config


@router.get("/{school_id}/license", response_model=SchoolLicenseOut)
async def get_school_license(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("license.view"))],
):
    await ensure_school_access(current_user, db, school_id)
    result = await db.execute(select(SchoolLicense).where(SchoolLicense.school_id == school_id))
    lic = result.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    data = {c.name: getattr(lic, c.name) for c in lic.__table__.columns}
    data["is_valid"] = lic.is_valid()
    return SchoolLicenseOut(**data)
