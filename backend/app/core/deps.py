from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import decode_token
from app.db.session import get_db
from app.models.license import SchoolLicense
from app.models.organization import Campus, Organization
from app.models.school import School
from app.models.session import UserSession
from app.models.user import Role, RolePermission, User, UserRole
from app.services.licensing import CORE_MODULES

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_role_codes(user: User) -> set[str]:
    return {assignment.role.code for assignment in user.roles if assignment.role}


def get_permission_codes(user: User) -> set[str]:
    if user.is_superuser:
        return {"*"}
    return {
        rp.permission.code
        for ur in user.roles
        if ur.role
        for rp in ur.role.permissions
        if rp.permission
    }


def has_permission(user: User, code: str) -> bool:
    return user.is_superuser or code in get_permission_codes(user)


async def ensure_user_tenant_active(user: User, db: AsyncSession) -> None:
    if user.is_superuser:
        return
    now = datetime.now(UTC)
    if user.organization_id:
        organization = await db.get(Organization, user.organization_id)
        if not organization:
            raise HTTPException(status_code=403, detail="Organization is unavailable")
        if organization.archived_at is not None:
            raise HTTPException(status_code=403, detail="Organization is archived")
        if not organization.is_active:
            raise HTTPException(status_code=403, detail="Organization is disabled")
        if organization.license_expires_at and organization.license_expires_at < now:
            raise HTTPException(status_code=403, detail="Organization license has expired")
        if organization.license_starts_at and organization.license_starts_at > now:
            raise HTTPException(status_code=403, detail="Organization license is not active yet")
    if user.school_id:
        school = await db.get(School, user.school_id)
        if not school or school.deleted_at is not None:
            raise HTTPException(status_code=403, detail="School/branch is archived")
        if not school.is_active:
            raise HTTPException(status_code=403, detail="School/branch is disabled")
        result = await db.execute(
            select(SchoolLicense).where(SchoolLicense.school_id == user.school_id)
        )
        license_ = result.scalar_one_or_none()
        if not license_ or not license_.is_valid():
            raise HTTPException(status_code=403, detail="School license is invalid or expired")


async def get_current_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise credentials_exception
    user_id = payload.get("sub")
    session_id = payload.get("sid")
    if not user_id or not session_id:
        raise credentials_exception
    try:
        parsed_user_id = UUID(user_id)
        parsed_session_id = UUID(session_id)
    except (TypeError, ValueError) as exc:
        raise credentials_exception from exc

    result = await db.execute(
        select(User)
        .options(
            selectinload(User.roles)
            .selectinload(UserRole.role)
            .selectinload(Role.permissions)
            .selectinload(RolePermission.permission)
        )
        .where(User.id == parsed_user_id)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception

    session = await db.get(UserSession, parsed_session_id)
    if session is None or session.user_id != user.id or not session.is_valid:
        raise credentials_exception

    await ensure_user_tenant_active(user, db)
    if user.must_change_password and request.url.path not in {
        "/api/v1/auth/me",
        "/api/v1/auth/change-password",
        "/api/v1/auth/logout",
    }:
        raise HTTPException(
            status_code=403,
            detail="Password change required before continuing. Open Account Security and set a new password.",
        )
    return user


async def get_current_active_superuser(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser privileges required")
    return current_user


def require_permissions(*required_codes: str):
    async def checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.is_superuser:
            return current_user
        user_perms = get_permission_codes(current_user)
        missing = [code for code in required_codes if code not in user_perms]
        if missing:
            raise HTTPException(
                status_code=403, detail=f"Missing permissions: {', '.join(missing)}"
            )
        return current_user

    return checker


async def ensure_organization_access(user: User, organization_id: UUID) -> None:
    """Restrict organization-level management actions to Organization Admin / Super Admin."""
    if user.is_superuser:
        return
    if "ORGANIZATION_ADMIN" in get_role_codes(user) and user.organization_id == organization_id:
        return
    raise HTTPException(status_code=403, detail="Organization access denied")


async def ensure_organization_read_access(user: User, organization_id: UUID) -> None:
    """Allow scoped admin users to read shared organization configuration.

    Academic Years are organization-wide. School / Branch Admins therefore need
    read-only visibility of the Organization Academic Year and its state while
    create/edit/activate operations remain guarded by ensure_organization_access.
    """
    if user.is_superuser:
        return
    role_codes = get_role_codes(user)
    if user.organization_id == organization_id and role_codes.intersection(
        {"ORGANIZATION_ADMIN", "SCHOOL_ADMIN"}
    ):
        return
    raise HTTPException(status_code=403, detail="Organization access denied")


async def ensure_school_access(user: User, db: AsyncSession, school_id: UUID) -> School:
    school = await db.get(School, school_id)
    if not school or school.deleted_at is not None:
        raise HTTPException(status_code=404, detail="School not found")
    if user.is_superuser:
        return school
    role_codes = get_role_codes(user)
    if (
        "ORGANIZATION_ADMIN" in role_codes
        and user.organization_id
        and school.organization_id == user.organization_id
    ):
        return school
    if user.school_id == school_id:
        return school
    raise HTTPException(status_code=403, detail="School access denied")


async def ensure_campus_access(user: User, db: AsyncSession, campus_id: UUID) -> Campus:
    campus = await db.get(Campus, campus_id)
    if not campus:
        raise HTTPException(status_code=404, detail="Campus not found")
    school = await db.get(School, campus.school_id)
    if not school or school.deleted_at is not None:
        raise HTTPException(status_code=404, detail="School not found")
    if user.is_superuser:
        return campus
    role_codes = get_role_codes(user)
    if (
        "ORGANIZATION_ADMIN" in role_codes
        and user.organization_id
        and school.organization_id == user.organization_id
    ):
        return campus
    if user.account_type == "SCHOOL_ADMIN" and user.school_id == school.id:
        return campus
    if user.campus_id == campus_id:
        return campus
    raise HTTPException(status_code=403, detail="Campus access denied")


async def get_school_or_404(
    school_id: UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> School:
    result = await db.execute(
        select(School).where(School.id == school_id, School.deleted_at.is_(None))
    )
    school = result.scalar_one_or_none()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    return school


async def ensure_license_valid(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    required_module: str | None = None,
) -> SchoolLicense:
    school = await db.get(School, school_id)
    if not school or school.deleted_at is not None:
        raise HTTPException(status_code=404, detail="School not found")
    if not school.is_active:
        raise HTTPException(status_code=403, detail="School/branch is disabled")
    if school.organization_id:
        organization = await db.get(Organization, school.organization_id)
        now = datetime.now(UTC)
        if not organization:
            raise HTTPException(status_code=403, detail="Organization is unavailable")
        if organization.archived_at is not None:
            raise HTTPException(status_code=403, detail="Organization is archived")
        if not organization.is_active:
            raise HTTPException(status_code=403, detail="Organization is disabled")
        if organization.license_starts_at and organization.license_starts_at > now:
            raise HTTPException(status_code=403, detail="Organization license is not active yet")
        if organization.license_expires_at and organization.license_expires_at < now:
            raise HTTPException(status_code=403, detail="Organization license has expired")
        if (
            required_module
            and required_module not in CORE_MODULES
            and required_module not in (organization.enabled_modules or [])
        ):
            raise HTTPException(
                status_code=403,
                detail=f"Module '{required_module}' is disabled for this organization",
            )
    result = await db.execute(select(SchoolLicense).where(SchoolLicense.school_id == school_id))
    license_ = result.scalar_one_or_none()
    if not license_ or not license_.is_valid():
        raise HTTPException(status_code=403, detail="School license is invalid or expired")
    if (
        required_module
        and required_module not in CORE_MODULES
        and not license_.has_module(required_module)
    ):
        raise HTTPException(
            status_code=403, detail=f"Module '{required_module}' is disabled for this school"
        )
    return license_
