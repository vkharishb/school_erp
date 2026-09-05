from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import ensure_school_access, get_role_codes, require_permissions
from app.db.session import get_db
from app.models.audit import AuditEvent
from app.models.user import User

router = APIRouter(prefix="/audit", tags=["Audit"])

ADMIN_AUDIT_ROLES = frozenset({"ORGANIZATION_ADMIN", "SCHOOL_ADMIN"})


def ensure_admin_audit_access(user: User) -> None:
    """Allow audit viewing only to platform, organization, and school admins."""
    if user.is_superuser:
        return
    if get_role_codes(user).intersection(ADMIN_AUDIT_ROLES):
        return
    raise HTTPException(
        status_code=403,
        detail="Audit logs are restricted to Platform Super Admin, Organization Admin, and School Admin",
    )


@router.get("", response_model=list[dict])
async def list_audit_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("audit.view"))],
    school_id: UUID | None = None,
    limit: int = 100,
):
    ensure_admin_audit_access(user)
    target_school = school_id or user.school_id
    if target_school:
        await ensure_school_access(user, db, target_school)
        query = (
            select(AuditEvent, User.full_name, User.username, User.account_type)
            .outerjoin(User, User.id == AuditEvent.user_id)
            .where(AuditEvent.school_id == target_school)
        )
    elif user.is_superuser:
        query = select(AuditEvent, User.full_name, User.username, User.account_type).outerjoin(
            User, User.id == AuditEvent.user_id
        )
    elif "ORGANIZATION_ADMIN" in get_role_codes(user):
        query = (
            select(AuditEvent, User.full_name, User.username, User.account_type)
            .outerjoin(User, User.id == AuditEvent.user_id)
            .where(AuditEvent.organization_id == user.organization_id)
        )
    else:
        raise HTTPException(status_code=403, detail="Audit scope is not assigned")
    query = query.order_by(AuditEvent.created_at.desc()).limit(min(limit, 500))
    result = await db.execute(query)
    return [
        {
            "id": str(item.id),
            "action": item.action,
            "module": item.module,
            "entity_type": item.entity_type,
            "entity_id": item.entity_id,
            "user_id": str(item.user_id) if item.user_id else None,
            "user_name": (item.metadata_json or {}).get("actor_name") or user_name,
            "username": (item.metadata_json or {}).get("actor_username") or username,
            "user_account_type": (item.metadata_json or {}).get("actor_account_type")
            or account_type,
            "before": item.before_data,
            "after": item.after_data,
            "metadata": item.metadata_json,
            "created_at": item.created_at.isoformat(),
        }
        for item, user_name, username, account_type in result.all()
    ]
