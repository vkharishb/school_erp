from typing import Any
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.user import User


async def record_audit(
    db: AsyncSession,
    *,
    action: str,
    user: User | None = None,
    module: str | None = None,
    entity_type: str | None = None,
    entity_id: str | UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    request: Request | None = None,
    target_organization_id: UUID | None = None,
    target_school_id: UUID | None = None,
    target_campus_id: UUID | None = None,
) -> AuditEvent:
    """Record an immutable audit event using the target tenant scope when supplied.

    This makes Platform Super Admin actions visible in the affected school's audit trail
    instead of being lost under the actor's global/null scope.
    """
    if user is not None:
        metadata = {
            **(metadata or {}),
            "actor_name": user.full_name,
            "actor_username": user.username,
            "actor_account_type": user.account_type,
        }
    if request is not None:
        reason = (request.headers.get("X-Change-Reason") or "").strip()
        if reason:
            metadata = {**(metadata or {}), "change_reason": reason}
        request.state.audit_recorded = True
    event = AuditEvent(
        organization_id=target_organization_id
        if target_organization_id is not None
        else (user.organization_id if user else None),
        school_id=target_school_id
        if target_school_id is not None
        else (user.school_id if user else None),
        campus_id=target_campus_id
        if target_campus_id is not None
        else (user.campus_id if user else None),
        user_id=user.id if user else None,
        action=action,
        module=module,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        before_data=before,
        after_data=after,
        metadata_json=metadata,
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request else None,
        correlation_id=str(uuid4()),
    )
    db.add(event)
    await db.flush()
    return event
