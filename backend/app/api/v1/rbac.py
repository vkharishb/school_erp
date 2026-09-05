from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_active_superuser, require_permissions
from app.db.session import get_db
from app.models.user import Permission, Role, RolePermission, User
from app.services.audit import record_audit

router = APIRouter(prefix="/rbac", tags=["Roles & Permissions"])

SUPER_ADMIN = "SUPER_ADMIN"
PREDEFINED_ROLES = [
    "SUPER_ADMIN",
    "ORGANIZATION_ADMIN",
    "SCHOOL_ADMIN",
    "ACCOUNTS",
    "TEACHER",
    "RECEPTIONIST",
    "PARENT_STUDENT",
]
PLATFORM_ONLY_PERMISSIONS = {
    "role.manage",
    "module.manage",
    "system.settings.manage",
    "organization.create",
    "organization.status.manage",
    "license.manage",
}


class PermissionOut(BaseModel):
    id: UUID
    code: str
    name: str
    module: str
    description: str | None = None


class RoleOut(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None = None
    is_system: bool
    school_id: UUID | None = None
    organization_id: UUID | None = None
    campus_id: UUID | None = None
    permissions: list[str]


class AssignableRoleOut(BaseModel):
    code: str
    name: str


class RolePermissionsUpdate(BaseModel):
    permission_codes: list[str]


class CustomRoleCreate(BaseModel):
    code: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(None, max_length=500)
    organization_id: UUID | None = None
    school_id: UUID | None = None
    permission_codes: list[str] = Field(default_factory=list)


def _role_out(role: Role) -> RoleOut:
    return RoleOut(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        school_id=role.school_id,
        organization_id=role.organization_id,
        campus_id=role.campus_id,
        permissions=sorted(rp.permission.code for rp in role.permissions if rp.permission),
    )


async def _permissions(db: AsyncSession, codes: list[str]) -> list[Permission]:
    requested = sorted(set(codes))
    result = await db.execute(select(Permission).where(Permission.code.in_(requested)))
    rows = list(result.scalars().all())
    found = {p.code for p in rows}
    missing = sorted(set(requested) - found)
    if missing:
        raise HTTPException(status_code=422, detail=f"Unknown permissions: {', '.join(missing)}")
    forbidden = sorted(set(requested) & PLATFORM_ONLY_PERMISSIONS)
    if forbidden:
        raise HTTPException(
            status_code=422,
            detail=f"Platform-only permissions cannot be assigned to a custom tenant role: {', '.join(forbidden)}",
        )
    return rows


@router.get("/permissions", response_model=list[PermissionOut])
async def list_permissions(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_active_superuser)],
):
    result = await db.execute(select(Permission).order_by(Permission.module, Permission.code))
    return [PermissionOut.model_validate(p, from_attributes=True) for p in result.scalars().all()]


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(get_current_active_superuser)],
    school_id: UUID | None = None,
):
    query = select(Role).options(
        selectinload(Role.permissions).selectinload(RolePermission.permission)
    )
    if school_id:
        query = query.where((Role.school_id.is_(None)) | (Role.school_id == school_id))
    result = await db.execute(query.order_by(Role.is_system.desc(), Role.name))
    return [_role_out(role) for role in result.scalars().unique().all()]


@router.get("/assignable-roles", response_model=list[AssignableRoleOut])
async def assignable_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_permissions("user.create"))],
):
    if actor.is_superuser:
        query = select(Role).where(Role.code != SUPER_ADMIN)
    elif actor.account_type == "ORGANIZATION_ADMIN":
        query = select(Role).where(
            Role.is_system.is_(True),
            Role.code.in_({"SCHOOL_ADMIN", "ACCOUNTS", "TEACHER", "RECEPTIONIST"}),
        )
    elif actor.account_type == "SCHOOL_ADMIN":
        query = select(Role).where(
            Role.is_system.is_(True), Role.code.in_({"ACCOUNTS", "TEACHER", "RECEPTIONIST"})
        )
    else:
        raise HTTPException(status_code=403, detail="Role assignment access denied")
    result = await db.execute(query.order_by(Role.name))
    return [AssignableRoleOut(code=r.code, name=r.name) for r in result.scalars().all()]


@router.post("/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
async def create_custom_role(
    payload: CustomRoleCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(get_current_active_superuser)],
):
    code = payload.code.strip().upper()
    if code in PREDEFINED_ROLES:
        raise HTTPException(status_code=409, detail="Predefined system role codes are protected")
    exists = await db.execute(
        select(Role.id).where(Role.code == code, Role.school_id == payload.school_id)
    )
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Custom role code already exists")
    permissions = await _permissions(db, payload.permission_codes)
    role = Role(
        code=code,
        name=payload.name.strip(),
        description=payload.description,
        is_system=False,
        organization_id=payload.organization_id,
        school_id=payload.school_id,
    )
    db.add(role)
    await db.flush()
    for permission in permissions:
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    await db.flush()
    loaded = (
        await db.execute(
            select(Role)
            .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
            .where(Role.id == role.id)
        )
    ).scalar_one()
    await record_audit(
        db,
        action="role.custom.created",
        user=actor,
        module="school_admin",
        entity_type="Role",
        entity_id=role.id,
        after={
            "code": role.code,
            "name": role.name,
            "permissions": sorted(payload.permission_codes),
        },
        request=request,
        target_organization_id=payload.organization_id,
        target_school_id=payload.school_id,
    )
    return _role_out(loaded)


@router.patch("/roles/{role_id}/permissions", response_model=RoleOut)
async def update_role_permissions(
    role_id: UUID,
    payload: RolePermissionsUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(get_current_active_superuser)],
):
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
        .where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system:
        raise HTTPException(
            status_code=409,
            detail="Predefined user-type permissions are protected. Create a custom role instead.",
        )
    permissions = await _permissions(db, payload.permission_codes)
    before = sorted(rp.permission.code for rp in role.permissions if rp.permission)
    role.permissions.clear()
    await db.flush()
    for permission in permissions:
        role.permissions.append(RolePermission(permission_id=permission.id))
    await db.flush()
    refreshed = (
        await db.execute(
            select(Role)
            .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
            .where(Role.id == role.id)
        )
    ).scalar_one()
    after = sorted(rp.permission.code for rp in refreshed.permissions if rp.permission)
    await record_audit(
        db,
        action="role.permissions.updated",
        user=actor,
        module="school_admin",
        entity_type="Role",
        entity_id=role.id,
        before={"permissions": before},
        after={"permissions": after},
        request=request,
        target_organization_id=role.organization_id,
        target_school_id=role.school_id,
    )
    return _role_out(refreshed)
