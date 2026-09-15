from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value

from app.core.security import decode_token
from app.db.session import get_db
from app.models.license import SchoolLicense
from app.models.organization import Campus, Organization
from app.models.school import School
from app.models.session import UserSession
from app.models.subscription import OrganizationSubscription, SchoolSubscription
from app.models.user import Role, RolePermission, User, UserRole

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
    if user.organization_id:
        organization = await db.get(Organization, user.organization_id)
        if not organization:
            raise HTTPException(status_code=403, detail="Organization is unavailable")
        if organization.archived_at is not None:
            raise HTTPException(status_code=403, detail="Organization is archived")
        if not organization.is_active:
            raise HTTPException(status_code=403, detail="Organization is disabled")
    if user.school_id:
        school = await db.get(School, user.school_id)
        if not school or school.deleted_at is not None:
            raise HTTPException(status_code=403, detail="School/branch is archived")
        if not school.is_active:
            raise HTTPException(status_code=403, detail="School/branch is disabled")
        trial_expiry = (
            await db.execute(
                select(SchoolSubscription.expires_at)
                .join(
                    OrganizationSubscription,
                    OrganizationSubscription.id
                    == SchoolSubscription.organization_subscription_id,
                )
                .where(
                    SchoolSubscription.school_id == user.school_id,
                    OrganizationSubscription.billing_cycle == "trial",
                    SchoolSubscription.status == "trial",
                )
                .order_by(SchoolSubscription.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if trial_expiry and trial_expiry <= datetime.now(UTC):
            raise HTTPException(
                status_code=403,
                detail="The 30-day trial has expired. Contact the Organization Admin to upgrade.",
            )
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

    # Campus assignments are retained in the database only as legacy metadata.
    # They must never narrow authorization or operational visibility. Present the
    # authenticated principal as School-scoped without dirtying the ORM object.
    if user.campus_id is not None:
        set_committed_value(user, "campus_id", None)

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


async def get_school_compatibility_campus(db: AsyncSession, school_id: UUID) -> Campus:
    """Return the hidden compatibility row used by legacy campus-keyed tables.

    Campus is no longer an authorization or UI scope. New school-scoped records are
    attached to MAIN only until the legacy foreign keys are retired in a later
    physical-schema cleanup. Existing campus rows remain untouched for data safety.
    """
    result = await db.execute(
        select(Campus)
        .where(Campus.school_id == school_id, Campus.is_active.is_(True))
        .order_by((Campus.code == "MAIN").desc(), Campus.created_at)
    )
    campus = result.scalars().first()
    if not campus:
        raise HTTPException(
            status_code=409,
            detail="School academic compatibility record is missing. Run the latest database migration.",
        )
    return campus


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
    # School-scoped operational users may intentionally have no campus_id.
    # In that case their data scope is the whole School, so any campus that
    # belongs to that School is accessible. Users with an explicit campus_id
    # remain restricted to that campus.
    if user.school_id == school.id and user.campus_id is None:
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
        if not organization:
            raise HTTPException(status_code=403, detail="Organization is unavailable")
        if organization.archived_at is not None:
            raise HTTPException(status_code=403, detail="Organization is archived")
        if not organization.is_active:
            raise HTTPException(status_code=403, detail="Organization is disabled")
    entitlement = (
        await db.execute(
            select(SchoolSubscription)
            .where(SchoolSubscription.school_id == school_id)
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
                status_code=403,
                detail="School ERP activation is pending. Complete activation before using subscription modules.",
            )
    result = await db.execute(select(SchoolLicense).where(SchoolLicense.school_id == school_id))
    license_ = result.scalar_one_or_none()
    if not license_ or not license_.is_valid():
        raise HTTPException(status_code=403, detail="School license is invalid or expired")
    if required_module and not license_.has_module(required_module):
        raise HTTPException(
            status_code=403, detail=f"Module '{required_module}' is disabled for this school"
        )
    return license_


async def ensure_download_allowed(school_id: UUID, db: AsyncSession) -> None:
    """Trial schools may use restricted ERP screens but cannot download/export data."""
    result = await db.execute(
        select(OrganizationSubscription.billing_cycle)
        .join(
            SchoolSubscription,
            SchoolSubscription.organization_subscription_id == OrganizationSubscription.id,
        )
        .where(
            SchoolSubscription.school_id == school_id,
            SchoolSubscription.status == "trial",
        )
        .order_by(SchoolSubscription.created_at.desc())
        .limit(1)
    )
    if result.scalar_one_or_none() == "trial":
        raise HTTPException(
            status_code=403,
            detail="Downloads and exports are unavailable during the 30-day trial",
        )
