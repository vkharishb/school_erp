import secrets
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
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
    normalize_area_code,
    school_prefix,
)
from app.core.security import get_password_hash
from app.core.usernames import normalize_username
from app.db.session import get_db
from app.models.governance import SchoolCodeRegistry
from app.models.license import SchoolLicense
from app.models.organization import AcademicYear, Campus, Organization, OrganizationAcademicYear
from app.models.school import School, SchoolConfiguration, SchoolUDISECode
from app.models.user import Role, User, UserRole
from app.schemas.license import SchoolLicenseOut, SchoolLicenseUpdate
from app.schemas.school import (
    SchoolConfigurationOut,
    SchoolConfigurationUpdate,
    SchoolCreate,
    SchoolOut,
    SchoolProfileUpdate,
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
    require_core_modules,
)
from app.services.password_policy import validate_password
from app.services.session_control import revoke_school_sessions

router = APIRouter(prefix="/schools", tags=["Schools"])


def _generate_license_key() -> str:
    return f"SERP-{secrets.token_hex(16).upper()}"


async def _next_school_code(
    db: AsyncSession,
    *,
    organization_id: UUID,
    school_name: str,
    area: str,
    requested_area_code: str | None,
) -> tuple[str, str]:
    prefix = school_prefix(school_name)
    location = (
        normalize_area_code(requested_area_code) if requested_area_code else area_short_code(area)
    )
    result = await db.execute(
        select(SchoolCodeRegistry.code).where(
            SchoolCodeRegistry.organization_id == organization_id,
            SchoolCodeRegistry.code.like(f"{prefix}-{location}-%"),
        )
    )
    numbers: list[int] = []
    for code in result.scalars().all():
        try:
            numbers.append(int(str(code).rsplit("-", 1)[1]))
        except (ValueError, IndexError):
            continue
    return format_school_code(prefix, location, max(numbers, default=0) + 1), location


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
    actor: Annotated[User, Depends(require_permissions("school.admin.edit"))],
):
    if not (actor.is_superuser or actor.account_type == "ORGANIZATION_ADMIN"):
        raise HTTPException(
            status_code=403,
            detail="Only Organization Admin or Super Admin can create Schools / Branches",
        )
    organization = await db.get(Organization, payload.organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    if not actor.is_superuser and actor.organization_id != organization.id:
        raise HTTPException(status_code=403, detail="Organization access denied")
    if organization.archived_at is not None:
        raise HTTPException(
            status_code=409, detail="Cannot create a School under an archived Organization"
        )
    if not organization.is_active:
        raise HTTPException(
            status_code=409, detail="Cannot create a School under a disabled Organization"
        )
    if organization.license_expires_at and organization.license_expires_at < datetime.now(UTC):
        raise HTTPException(
            status_code=409, detail="Cannot create a School under an expired Organization license"
        )

    active_count = int(
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
    if not actor.is_superuser and active_count >= organization.allowed_schools:
        raise HTTPException(
            status_code=409,
            detail=f"Organization School limit reached ({organization.allowed_schools}). Contact Super Admin to increase the allowed number of Schools.",
        )

    admin_username = None
    school_admin_role = None
    if payload.admin:
        admin_username = normalize_username(payload.admin.username)
        validate_password(payload.admin.password, username=admin_username)
        duplicate_user = await db.execute(
            select(User.id).where(func.lower(User.username) == admin_username)
        )
        if duplicate_user.scalar_one_or_none():
            raise HTTPException(
                status_code=409, detail="School / Branch Admin username already exists"
            )
        role_result = await db.execute(
            select(Role).where(Role.code == "SCHOOL_ADMIN", Role.school_id.is_(None))
        )
        school_admin_role = role_result.scalars().first()
        if not school_admin_role:
            raise HTTPException(
                status_code=500, detail="School / Branch Admin system role is not initialized"
            )

    code, generated_area_code = await _next_school_code(
        db,
        organization_id=organization.id,
        school_name=payload.configuration.name,
        area=payload.configuration.area,
        requested_area_code=payload.configuration.area_code,
    )
    # ERP code may never be reused, including archived historical rows. Reserve it
    # in the permanent registry before the School is created. The unique registry
    # constraint also protects against concurrent creation races.
    duplicate_code = await db.execute(
        select(SchoolCodeRegistry.id).where(
            SchoolCodeRegistry.organization_id == organization.id,
            SchoolCodeRegistry.code == code,
        )
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
    school = School(code=code, udise_code=primary_udise, organization_id=organization.id)
    db.add(school)
    await db.flush()
    registry.issued_school_id = school.id

    config_data = payload.configuration.model_dump()
    config_data["area_code"] = generated_area_code
    if payload.admin:
        config_data["principal_head_name"] = (
            config_data.get("principal_head_name") or payload.admin.full_name.strip()
        )
        config_data["principal_head_email"] = (
            config_data.get("principal_head_email") or payload.admin.email
        )
        config_data["principal_head_phone"] = (
            config_data.get("principal_head_phone") or payload.admin.phone
        )
    config = SchoolConfiguration(school_id=school.id, **config_data)
    db.add(config)
    for item in udise_values:
        db.add(
            SchoolUDISECode(
                school_id=school.id,
                udise_code=item.udise_code,
                label=item.label,
                is_primary=item.is_primary,
                is_active=True,
            )
        )

    now = datetime.now(UTC)
    requested_modules = payload.enabled_modules or list(PHASE1_MODULES)
    unavailable = sorted(set(requested_modules) - IMPLEMENTED_MODULES)
    if unavailable:
        raise HTTPException(
            status_code=409, detail=f"Modules not implemented yet: {', '.join(unavailable)}"
        )
    try:
        require_core_modules(requested_modules)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if organization.enabled_modules:
        invalid = sorted(set(requested_modules) - set(organization.enabled_modules))
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"Modules not enabled for Organization: {', '.join(invalid)}",
            )
    expiry = payload.license_expires_at or organization.license_expires_at or next_may_31(now)
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

    school_admin = None
    if payload.admin and admin_username and school_admin_role:
        school_admin = User(
            username=admin_username,
            account_type="SCHOOL_ADMIN",
            email=str(payload.admin.email) if payload.admin.email else None,
            hashed_password=get_password_hash(payload.admin.password),
            full_name=payload.admin.full_name.strip(),
            designation=payload.admin.designation,
            phone=payload.admin.phone,
            organization_id=organization.id,
            school_id=school.id,
            campus_id=None,
            is_superuser=False,
            is_active=True,
            must_change_password=True,
        )
        db.add(school_admin)
        await db.flush()
        db.add(UserRole(user_id=school_admin.id, role_id=school_admin_role.id))
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
            "school_admin_username": school_admin.username if school_admin else None,
            "school_admin_full_name": school_admin.full_name if school_admin else None,
            "school_admin_designation": school_admin.designation if school_admin else None,
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
    user: Annotated[User, Depends(require_permissions("school.admin.edit"))],
):
    if not (user.is_superuser or user.account_type == "ORGANIZATION_ADMIN"):
        raise HTTPException(
            status_code=403,
            detail="Only Organization Admin or Super Admin can change School status",
        )
    school = await db.get(School, school_id)
    if not school or school.deleted_at is not None:
        raise HTTPException(status_code=404, detail="School not found")
    if not user.is_superuser and school.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="School access denied")
    if payload.is_active is None:
        raise HTTPException(status_code=422, detail="is_active is required")
    if payload.is_active and school.organization_id:
        organization = await db.get(Organization, school.organization_id)
        if not organization or organization.archived_at is not None:
            raise HTTPException(
                status_code=409,
                detail="Organization is archived. Restore it before enabling this School.",
            )
        if not organization.is_active:
            raise HTTPException(
                status_code=409,
                detail="Organization is disabled. Please activate the Organization before enabling this School.",
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
        request=request,
        target_organization_id=school.organization_id,
        target_school_id=school.id,
    )
    await db.flush()
    return _require_reloaded_school(await _load_school(db, school.id))


@router.post("/{school_id}/archive", response_model=SchoolOut)
async def archive_school(
    school_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("school.admin.edit"))],
):
    if not (user.is_superuser or user.account_type == "ORGANIZATION_ADMIN"):
        raise HTTPException(
            status_code=403,
            detail="Only Organization Admin or Super Admin can archive Schools / Branches",
        )
    school = await db.get(School, school_id)
    if not school or school.deleted_at is not None:
        raise HTTPException(status_code=404, detail="School not found")
    if not user.is_superuser and school.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="School access denied")
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
        metadata={"sessions_revoked": revoked},
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
    user: Annotated[User, Depends(require_permissions("school.admin.edit"))],
):
    if not (user.is_superuser or user.account_type == "ORGANIZATION_ADMIN"):
        raise HTTPException(
            status_code=403,
            detail="Only Organization Admin or Super Admin can restore Schools / Branches",
        )
    school = await _load_school(db, school_id, include_deleted=True)
    if not school or school.deleted_at is None:
        raise HTTPException(status_code=404, detail="Archived School not found")
    if not user.is_superuser and school.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="School access denied")
    organization = (
        await db.get(Organization, school.organization_id) if school.organization_id else None
    )
    if organization and organization.archived_at is not None:
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
            skipped_udise += 1
            continue
        row.deleted_at = None
        row.is_active = True
        row.is_primary = row.udise_code == school.udise_code
        restored_udise += 1
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
    await archive_school(school_id, request, db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
        try:
            require_core_modules(payload.enabled_modules)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        allowed = (
            set(organization.enabled_modules or [])
            if organization
            else set(payload.enabled_modules)
        )
        invalid = sorted(set(payload.enabled_modules) - allowed)
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"Modules not enabled for Organization: {', '.join(invalid)}",
            )
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
    # ERP code/area short code is immutable after School creation.
    if "area_code" in changes and changes["area_code"] != config.area_code:
        raise HTTPException(
            status_code=409, detail="ERP Area Short Code is immutable after School creation"
        )
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
    if "area_code" in update_data and update_data["area_code"] != config.area_code:
        raise HTTPException(
            status_code=409, detail="ERP Area Short Code is immutable after School creation"
        )
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
