from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_role_codes, require_permissions
from app.core.security import get_password_hash
from app.core.usernames import normalize_username
from app.db.session import get_db
from app.models.license import SchoolLicense
from app.models.organization import Campus
from app.models.school import School
from app.models.session import UserSession
from app.models.user import Role, User, UserRole
from app.schemas.user import (
    ManagedUserOut,
    PasswordResetRequest,
    UserCreate,
    UserUpdate,
    validate_admin_designation,
)
from app.services.audit import record_audit
from app.services.password_policy import validate_password

router = APIRouter(prefix="/users", tags=["User Administration"])

SUPER_ADMIN = "SUPER_ADMIN"
ORGANIZATION_ADMIN = "ORGANIZATION_ADMIN"
SCHOOL_ADMIN = "SCHOOL_ADMIN"
STANDARD_SCHOOL_TYPES = {"SCHOOL_ADMIN", "ACCOUNTS", "TEACHER", "RECEPTIONIST", "PARENT_STUDENT"}
FUNCTIONAL_TYPES = {"ACCOUNTS", "TEACHER", "RECEPTIONIST", "PARENT_STUDENT"}


def _to_out(user: User) -> ManagedUserOut:
    return ManagedUserOut(
        id=user.id,
        username=user.username,
        account_type=user.account_type,
        email=user.email,
        full_name=user.full_name,
        designation=user.designation,
        phone=user.phone,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        must_change_password=user.must_change_password,
        organization_id=user.organization_id,
        school_id=user.school_id,
        campus_id=user.campus_id,
        last_login_at=user.last_login_at,
        roles=sorted(get_role_codes(user)),
    )


async def _validate_scope_links(
    db: AsyncSession, payload: UserCreate
) -> tuple[School | None, Campus | None]:
    school = await db.get(School, payload.school_id) if payload.school_id else None
    if payload.school_id and (not school or school.deleted_at is not None):
        raise HTTPException(status_code=404, detail="School not found")
    if school and school.organization_id != payload.organization_id:
        raise HTTPException(status_code=422, detail="School does not belong to Organization")
    campus = await db.get(Campus, payload.campus_id) if payload.campus_id else None
    if payload.campus_id and not campus:
        raise HTTPException(status_code=404, detail="Campus not found")
    if campus and campus.school_id != payload.school_id:
        raise HTTPException(status_code=422, detail="Campus does not belong to School")
    return school, campus


def _validate_actor_can_create(actor: User, payload: UserCreate) -> None:
    if actor.is_superuser:
        return
    if payload.account_type in {SUPER_ADMIN, ORGANIZATION_ADMIN}:
        raise HTTPException(status_code=403, detail="Only Super Admin can create this account type")
    if actor.account_type == ORGANIZATION_ADMIN:
        if payload.organization_id != actor.organization_id:
            raise HTTPException(status_code=403, detail="User must belong to your Organization")
        if payload.account_type not in STANDARD_SCHOOL_TYPES:
            raise HTTPException(
                status_code=403, detail="Account type cannot be assigned by Organization Admin"
            )
        return
    if actor.account_type == SCHOOL_ADMIN:
        if payload.school_id != actor.school_id:
            raise HTTPException(status_code=403, detail="User must belong to your School / Branch")
        if payload.account_type not in FUNCTIONAL_TYPES:
            raise HTTPException(
                status_code=403, detail="Account type cannot be assigned by School Admin"
            )
        return
    raise HTTPException(status_code=403, detail="User administration access denied")


async def _load_role(db: AsyncSession, code: str) -> Role:
    result = await db.execute(select(Role).where(Role.code == code, Role.school_id.is_(None)))
    role = result.scalars().first()
    if not role:
        raise HTTPException(status_code=422, detail=f"Unknown role: {code}")
    return role


async def _load_roles(db: AsyncSession, codes: set[str]) -> list[Role]:
    if not codes:
        return []
    result = await db.execute(select(Role).where(Role.code.in_(codes)))
    roles = list(result.scalars().all())
    found = {r.code for r in roles}
    missing = sorted(codes - found)
    if missing:
        raise HTTPException(status_code=422, detail=f"Unknown roles: {', '.join(missing)}")
    return roles


async def _load_user_with_roles(db: AsyncSession, user_id: UUID) -> User:
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _assert_manage_scope(actor: User, target: User) -> None:
    if actor.is_superuser:
        return
    if target.is_superuser or target.account_type == SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Super Admin cannot be modified")
    if actor.account_type == ORGANIZATION_ADMIN:
        if target.organization_id != actor.organization_id:
            raise HTTPException(status_code=403, detail="User access denied")
        if target.account_type == ORGANIZATION_ADMIN:
            raise HTTPException(
                status_code=403, detail="Only Super Admin can modify Organization Admin"
            )
        return
    if actor.account_type == SCHOOL_ADMIN:
        if target.school_id != actor.school_id:
            raise HTTPException(status_code=403, detail="User access denied")
        if target.account_type not in FUNCTIONAL_TYPES:
            raise HTTPException(
                status_code=403, detail="School Admin cannot modify another administrator"
            )
        return
    raise HTTPException(status_code=403, detail="User administration access denied")


async def _revoke_user_sessions(db: AsyncSession, user_id: UUID, reason: str) -> int:
    now = datetime.now(UTC)
    result = await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.is_active.is_(True))
        .values(is_active=False, revoked_at=now, revocation_reason=reason)
    )
    return int(result.rowcount or 0)


@router.post("", response_model=ManagedUserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("user.create"))],
):
    _validate_actor_can_create(actor, payload)
    if payload.account_type == "PARENT_STUDENT":
        raise HTTPException(
            status_code=409,
            detail="Parent / Student accounts are created only through Student ERP Access opt-in using the School-selected access number",
        )
    school, _campus = await _validate_scope_links(db, payload)
    normalized_username = normalize_username(payload.username)
    validate_password(payload.password, username=normalized_username)

    if payload.account_type == SUPER_ADMIN and not actor.is_superuser:
        raise HTTPException(
            status_code=403, detail="Only Super Admin can create Super Admin accounts"
        )
    if payload.account_type == ORGANIZATION_ADMIN:
        if not payload.organization_id or payload.school_id or payload.campus_id:
            raise HTTPException(
                status_code=422, detail="Organization Admin must be scoped only to an Organization"
            )
    elif payload.account_type in STANDARD_SCHOOL_TYPES - {"PARENT_STUDENT"}:
        if not payload.organization_id or not payload.school_id:
            raise HTTPException(
                status_code=422, detail="Organization and School are required for this account type"
            )
    elif payload.account_type == "PARENT_STUDENT":
        if not payload.organization_id or not payload.phone:
            raise HTTPException(
                status_code=422, detail="Organization and access phone number are required"
            )

    if school:
        lic_result = await db.execute(
            select(SchoolLicense).where(SchoolLicense.school_id == school.id)
        )
        lic = lic_result.scalar_one_or_none()
        if not lic or not lic.is_valid():
            raise HTTPException(status_code=403, detail="School license is invalid or expired")
        count_result = await db.execute(
            select(func.count(User.id)).where(User.school_id == school.id, User.is_active.is_(True))
        )
        if int(count_result.scalar_one() or 0) >= lic.max_users:
            raise HTTPException(status_code=409, detail="School license user limit reached")

    duplicate = await db.execute(
        select(User.id).where(func.lower(User.username) == normalized_username)
    )
    if duplicate.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already exists")

    # Every user gets exactly one predefined base account-type role. Super Admin
    # may additionally attach a custom permission role/profile.
    base_role = await _load_role(db, payload.account_type)
    extra_codes = set(payload.role_codes or []) - {payload.account_type}
    if extra_codes and not actor.is_superuser:
        raise HTTPException(status_code=403, detail="Only Super Admin can assign customized roles")
    extra_roles = await _load_roles(db, extra_codes)

    user = User(
        username=normalized_username,
        account_type=payload.account_type,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        designation=payload.designation,
        phone=payload.phone,
        organization_id=payload.organization_id,
        school_id=payload.school_id,
        campus_id=payload.campus_id,
        is_superuser=payload.account_type == SUPER_ADMIN,
        must_change_password=True,
    )
    db.add(user)
    await db.flush()
    for role in [base_role, *extra_roles]:
        db.add(UserRole(user_id=user.id, role_id=role.id))
    await db.flush()
    created = await _load_user_with_roles(db, user.id)
    await record_audit(
        db,
        action="user.created",
        user=actor,
        module="school_admin",
        entity_type="User",
        entity_id=created.id,
        after={
            "username": created.username,
            "account_type": created.account_type,
            "roles": sorted(get_role_codes(created)),
            "school_id": str(created.school_id) if created.school_id else None,
        },
        request=request,
        target_organization_id=created.organization_id,
        target_school_id=created.school_id,
    )
    return _to_out(created)


@router.get("", response_model=list[ManagedUserOut])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("user.view"))],
    organization_id: UUID | None = None,
    school_id: UUID | None = None,
    campus_id: UUID | None = None,
    include_organization_admins: bool = False,
    limit: int = 100,
    offset: int = 0,
):
    if include_organization_admins and not actor.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="Only Platform Owner can include Organization Admin accounts",
        )
    if include_organization_admins and not school_id:
        raise HTTPException(
            status_code=422,
            detail="school_id is required when including Organization Admin accounts",
        )

    query = select(User).options(selectinload(User.roles).selectinload(UserRole.role))
    if actor.is_superuser:
        if organization_id:
            query = query.where(User.organization_id == organization_id)
    elif actor.account_type == ORGANIZATION_ADMIN:
        query = query.where(User.organization_id == actor.organization_id)
    elif actor.account_type == SCHOOL_ADMIN:
        query = query.where(User.school_id == actor.school_id)
    else:
        raise HTTPException(status_code=403, detail="User administration access denied")
    if school_id:
        if include_organization_admins:
            school = await db.get(School, school_id)
            if not school or school.deleted_at is not None:
                raise HTTPException(status_code=404, detail="School not found")
            query = query.where(
                or_(
                    User.school_id == school_id,
                    (
                        (User.organization_id == school.organization_id)
                        & (User.account_type == ORGANIZATION_ADMIN)
                        & User.school_id.is_(None)
                    ),
                )
            )
        else:
            query = query.where(User.school_id == school_id)
    if campus_id:
        query = query.where(User.campus_id == campus_id)
    result = await db.execute(query.order_by(User.full_name).offset(offset).limit(min(limit, 500)))
    return [_to_out(user) for user in result.scalars().unique().all()]


@router.patch("/{user_id}", response_model=ManagedUserOut)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("user.edit"))],
):
    target = await _load_user_with_roles(db, user_id)
    _assert_manage_scope(actor, target)
    before = {
        "is_active": target.is_active,
        "full_name": target.full_name,
        "designation": target.designation,
        "email": target.email,
        "phone": target.phone,
        "roles": sorted(get_role_codes(target)),
    }
    if target.id == actor.id and payload.is_active is False:
        raise HTTPException(status_code=409, detail="You cannot disable your own account")

    if "designation" in payload.model_fields_set:
        try:
            payload.designation = validate_admin_designation(
                target.account_type, payload.designation
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    update_data = payload.model_dump(exclude_unset=True, exclude={"role_codes"})
    for field, value in update_data.items():
        setattr(target, field, value)

    if payload.role_codes is not None:
        if not actor.is_superuser:
            raise HTTPException(
                status_code=403, detail="Only Super Admin can customize role assignments"
            )
        requested = set(payload.role_codes)
        requested.add(target.account_type)
        roles = await _load_roles(db, requested)
        target.roles.clear()
        await db.flush()
        for role in roles:
            target.roles.append(UserRole(role_id=role.id))

    revoked = 0
    if before["is_active"] and target.is_active is False:
        revoked = await _revoke_user_sessions(db, target.id, "account_disabled")
    await db.flush()
    after = {
        "is_active": target.is_active,
        "full_name": target.full_name,
        "designation": target.designation,
        "email": target.email,
        "phone": target.phone,
        "roles": sorted(get_role_codes(target)),
    }
    action = "user.updated"
    if before["is_active"] and not target.is_active:
        action = "user.disabled"
    elif not before["is_active"] and target.is_active:
        action = "user.enabled"
    await record_audit(
        db,
        action=action,
        user=actor,
        module="school_admin",
        entity_type="User",
        entity_id=target.id,
        before=before,
        after=after,
        metadata={"sessions_revoked": revoked} if revoked else None,
        request=request,
        target_organization_id=target.organization_id,
        target_school_id=target.school_id,
    )
    return _to_out(target)


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_user_password(
    user_id: UUID,
    payload: PasswordResetRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("user.edit"))],
):
    if not (actor.is_superuser or actor.account_type in {ORGANIZATION_ADMIN, SCHOOL_ADMIN}):
        raise HTTPException(
            status_code=403, detail="Password reset is available only to admin-level users"
        )
    target = await _load_user_with_roles(db, user_id)
    if actor.id == target.id:
        raise HTTPException(
            status_code=409, detail="Use Account Security to change your own password"
        )
    _assert_manage_scope(actor, target)
    validate_password(payload.new_password, username=target.username)
    target.hashed_password = get_password_hash(payload.new_password)
    target.must_change_password = True
    revoked = await _revoke_user_sessions(db, target.id, "password_reset")
    await db.flush()
    await record_audit(
        db,
        action="user.password.reset",
        user=actor,
        module="school_admin",
        entity_type="User",
        entity_id=target.id,
        after={
            "username": target.username,
            "sessions_revoked": revoked,
            "must_change_password": True,
        },
        request=request,
        target_organization_id=target.organization_id,
        target_school_id=target.school_id,
    )
    return None
