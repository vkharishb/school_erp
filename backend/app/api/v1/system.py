from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_active_superuser
from app.core.platform_catalog import PLATFORM_MODULES, module_status_summary
from app.core.security import verify_password
from app.db.session import AsyncSessionLocal, engine, get_db
from app.models import (
    AcademicClass,
    AcademicYear,
    AnnualCorrectionUsage,
    ApprovalRequest,
    AuditEvent,
    Campus,
    ERPAccessPolicy,
    FeeHead,
    FeeStructureItem,
    Guardian,
    Organization,
    OrganizationAcademicYear,
    ParentStudentLink,
    Payment,
    PaymentAllocation,
    ReceiptSequence,
    Role,
    School,
    SchoolCodeRegistry,
    SchoolConfiguration,
    SchoolLicense,
    SchoolUDISECode,
    Section,
    Student,
    StudentAttendance,
    StudentCharge,
    StudentEnrollment,
    StudentERPAccess,
    StudentGuardian,
    StudentMark,
    Subject,
    Teacher,
    TeacherAttendance,
    User,
    UserRole,
    UserSession,
)
from app.services.audit import record_audit
from app.services.backups import (
    backup_status,
    create_backup,
    delete_backup,
    get_backup_path,
    list_backups,
    restore_backup,
)

router = APIRouter(prefix="/system", tags=["System"])


class RestoreRequest(BaseModel):
    backup_name: str = Field(min_length=6, max_length=255)
    expected_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[A-Fa-f0-9]{64}$")
    confirmation: str


LOWER_ENVIRONMENTS = {"development", "dev", "local", "test", "ci", "qa", "staging", "uat"}
RESET_CONFIRMATION = "RESET DEVELOPMENT DATA"


class DevelopmentResetRequest(BaseModel):
    confirmation: str = Field(min_length=5, max_length=80)
    password: str = Field(min_length=1, max_length=128)


def _ensure_lower_environment() -> str:
    environment = get_settings().app_env.strip().lower()
    if environment not in LOWER_ENVIRONMENTS:
        raise HTTPException(
            status_code=403,
            detail="Development Data Reset is disabled outside approved lower environments.",
        )
    return environment


async def _count_rows(db: AsyncSession, model, *criteria) -> int:
    stmt = select(func.count()).select_from(model)
    if criteria:
        stmt = stmt.where(*criteria)
    return int((await db.execute(stmt)).scalar_one())


async def _development_reset_counts(db: AsyncSession, owner_id) -> dict[str, int]:
    return {
        "organizations": await _count_rows(db, Organization),
        "schools": await _count_rows(db, School),
        "campuses": await _count_rows(db, Campus),
        "users_except_platform_owner": await _count_rows(db, User, User.id != owner_id),
        "students": await _count_rows(db, Student),
        "teachers": await _count_rows(db, Teacher),
        "payments": await _count_rows(db, Payment),
        "audit_events": await _count_rows(db, AuditEvent),
    }


async def _clear_development_data(db: AsyncSession, owner: User) -> None:
    """Delete lower-environment tenant/business data while preserving platform code masters.

    Preserved: Alembic schema/history, module definitions, permission definitions, global
    system roles, and the Platform Owner user itself.  All sessions are revoked.
    """
    # Detach the preserved Platform Owner from any accidental tenant scope before
    # tenant roots are deleted. School FK uses CASCADE, so this is a hard safety rule.
    owner.organization_id = None
    owner.school_id = None
    owner.campus_id = None
    owner.is_active = True
    owner.is_superuser = True
    await db.flush()

    # Child / transactional records first.
    for model in (
        AuditEvent,
        ParentStudentLink,
        StudentERPAccess,
        ERPAccessPolicy,
        ApprovalRequest,
        AnnualCorrectionUsage,
        PaymentAllocation,
        Payment,
        StudentCharge,
        ReceiptSequence,
        FeeStructureItem,
        FeeHead,
        StudentMark,
        StudentAttendance,
        TeacherAttendance,
        StudentEnrollment,
        StudentGuardian,
        Guardian,
        Teacher,
        Student,
        Subject,
        Section,
        AcademicClass,
        AcademicYear,
        SchoolLicense,
        SchoolConfiguration,
        SchoolUDISECode,
        SchoolCodeRegistry,
        OrganizationAcademicYear,
        Campus,
    ):
        await db.execute(delete(model))

    # Remove all assignments and tenant/custom roles, then restore only the Platform
    # Owner's global SUPER_ADMIN assignment. Global system roles and permissions remain.
    await db.execute(delete(UserRole))
    await db.execute(
        delete(Role).where(
            or_(
                Role.is_system.is_(False),
                Role.school_id.is_not(None),
                Role.organization_id.is_not(None),
                Role.campus_id.is_not(None),
            )
        )
    )

    # Remove every non-owner user before tenant roots. Restrictive user references were
    # cleared above; SET NULL/CASCADE foreign keys handle any residual optional links.
    await db.execute(delete(User).where(User.id != owner.id))
    await db.execute(delete(School))
    await db.execute(delete(Organization))

    # Revoke all login sessions, including the current one. The caller must re-login.
    await db.execute(delete(UserSession))

    super_role = (
        await db.execute(
            select(Role).where(
                Role.code == "SUPER_ADMIN",
                Role.school_id.is_(None),
                Role.organization_id.is_(None),
                Role.campus_id.is_(None),
            )
        )
    ).scalar_one_or_none()
    if super_role is not None:
        db.add(UserRole(user_id=owner.id, role_id=super_role.id))
    await db.flush()


@router.get("/version")
async def system_version():
    return {
        "release": "V1.1.DEV.15",
        "migration_head": "025",
        "phase": 1,
        "navigation": [
            "School Administration",
            "Student Management",
            "Teacher Management",
            "Fee Management",
            "Marks",
            "Attendance",
            "Reports",
        ],
    }


@router.get("/settings")
async def system_settings(_: Annotated[User, Depends(get_current_active_superuser)]):
    settings = get_settings()
    return {
        "environment": settings.app_env,
        "platform_version": "V1.1.DEV.15",
        "migration_head": "025",
        "debug": settings.debug,
        "password_min_length": 10,
        "password_max_length": 128,
        "refresh_cookie_secure": settings.refresh_cookie_secure,
        "license_year_end": "31-May",
        "bulk_import_max_file_mb": 5,
        "bulk_import_max_rows": 2000,
        "backup_schedule_hours": settings.backup_schedule_hours,
        "backup_retention_count": settings.backup_retention_count,
        "backup_offsite_configured": bool(settings.backup_offsite_dir.strip()),
        "backup_daily_retention_days": settings.backup_daily_retention_days,
        "backup_weekly_retention_weeks": settings.backup_weekly_retention_weeks,
        "backup_monthly_retention_months": settings.backup_monthly_retention_months,
        "require_recent_backup_for_archive": settings.require_recent_backup_for_archive,
        "archive_backup_max_age_hours": settings.archive_backup_max_age_hours,
        "browser_restore_enabled": settings.browser_restore_enabled,
        "notes": "Security-sensitive values are code/environment managed. Secrets are never exposed.",
    }


@router.get("/platform-status")
async def platform_status(_: Annotated[User, Depends(get_current_active_superuser)]):
    settings = get_settings()
    summary = module_status_summary()
    return {
        "platform_status": "Development",
        "release": "V1.1.DEV.15",
        "migration_head": "025",
        "phase": 1,
        "environment": settings.app_env,
        "summary": summary,
        "modules": PLATFORM_MODULES,
    }


@router.get("/development-reset/preview")
async def development_reset_preview(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_superuser)],
):
    environment = _ensure_lower_environment()
    return {
        "enabled": True,
        "environment": environment,
        "confirmation_phrase": RESET_CONFIRMATION,
        "preserves": [
            "Platform Owner account",
            "Alembic schema and migration history",
            "Platform module catalog",
            "Permission definitions and global system roles",
            "Backup files",
        ],
        "deletes": await _development_reset_counts(db, user.id),
        "requires_relogin": True,
    }


@router.post("/development-reset")
async def development_data_reset(
    payload: DevelopmentResetRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_superuser)],
):
    environment = _ensure_lower_environment()
    if payload.confirmation != RESET_CONFIRMATION:
        raise HTTPException(
            status_code=422, detail=f"Confirmation phrase must be exactly {RESET_CONFIRMATION}"
        )
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Platform Owner password is incorrect")

    removed = await _development_reset_counts(db, user.id)
    try:
        safety_backup = await create_backup(label="pre-dev-reset")
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Safety backup failed; development data was NOT reset. {str(exc)[-400:]}",
        ) from exc

    await _clear_development_data(db, user)
    await record_audit(
        db,
        action="system.development_data_reset.completed",
        user=user,
        module="system",
        entity_type="DevelopmentEnvironment",
        entity_id=environment,
        after={"removed": removed, "safety_backup": safety_backup["name"]},
        metadata={"environment": environment, "requires_relogin": True},
        request=request,
    )
    await db.commit()
    return {
        "status": "reset_completed",
        "environment": environment,
        "removed": removed,
        "safety_backup": safety_backup["name"],
        "requires_relogin": True,
    }


@router.get("/backups")
async def backups(_: Annotated[User, Depends(get_current_active_superuser)]):
    settings = get_settings()
    return {
        "items": list_backups(),
        "schedule_hours": settings.backup_schedule_hours,
        "retention_count": settings.backup_retention_count,
        "status": backup_status(),
    }


@router.post("/backups", status_code=status.HTTP_201_CREATED)
async def manual_backup(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_superuser)],
):
    try:
        item = await create_backup(label="manual")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Backup failed: {str(exc)[-500:]}") from exc
    await record_audit(
        db,
        action="system.backup.created",
        user=user,
        module="system",
        entity_type="DatabaseBackup",
        entity_id=item["name"],
        after={"sha256": item["sha256"], "size_bytes": item["size_bytes"]},
        request=request,
    )
    return item


@router.get("/backups/{backup_name}/download")
async def download_backup(
    backup_name: str, _: Annotated[User, Depends(get_current_active_superuser)]
):
    try:
        path = get_backup_path(backup_name)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Backup not found") from exc
    return FileResponse(path, media_type="application/octet-stream", filename=path.name)


@router.delete("/backups/{backup_name}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_backup(
    backup_name: str,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_superuser)],
):
    try:
        delete_backup(backup_name)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Backup not found") from exc
    await record_audit(
        db,
        action="system.backup.deleted",
        user=user,
        module="system",
        entity_type="DatabaseBackup",
        entity_id=backup_name,
        request=request,
    )
    return None


@router.post("/restore", status_code=status.HTTP_202_ACCEPTED)
async def restore_database(
    payload: RestoreRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_superuser)],
):
    settings = get_settings()
    if not settings.browser_restore_enabled:
        raise HTTPException(
            status_code=403,
            detail="Browser restore is disabled. Enable BROWSER_RESTORE_ENABLED only during an approved maintenance window.",
        )
    if payload.confirmation != "RESTORE DATABASE":
        raise HTTPException(
            status_code=422, detail="Confirmation phrase must be exactly RESTORE DATABASE"
        )
    actor_id = user.id
    actor_username = user.username
    await record_audit(
        db,
        action="system.restore.requested",
        user=user,
        module="system",
        entity_type="DatabaseBackup",
        entity_id=payload.backup_name,
        request=request,
    )
    await db.commit()
    # Release pooled connections before pg_restore performs schema replacement.
    await engine.dispose()
    try:
        result = await restore_backup(payload.backup_name, payload.expected_sha256)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Restore failed: {str(exc)[-500:]}") from exc
    finally:
        # Force the next ORM operation to connect to the restored database state.
        await engine.dispose()

    # The restore may have replaced the Users table, so never reuse the pre-restore
    # ORM User object for the completion audit. Re-resolve the actor safely.
    async with AsyncSessionLocal() as audit_db:
        actor = await audit_db.get(User, actor_id)
        if actor is None:
            actor = (
                await audit_db.execute(
                    select(User).where(User.username == actor_username, User.is_superuser.is_(True))
                )
            ).scalar_one_or_none()
        await record_audit(
            audit_db,
            action="system.restore.completed",
            user=actor,
            module="system",
            entity_type="DatabaseBackup",
            entity_id=payload.backup_name,
            after={"sha256": result["sha256"], "safety_backup": result["safety_backup"]},
            metadata={"requested_by_username": actor_username},
            request=request,
        )
        await audit_db.commit()
    return result
