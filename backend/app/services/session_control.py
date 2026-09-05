from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import UserSession
from app.models.user import User


async def revoke_user_sessions(db: AsyncSession, user_id: UUID, reason: str) -> int:
    now = datetime.now(UTC)
    result = await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.is_active.is_(True))
        .values(is_active=False, revoked_at=now, revocation_reason=reason)
    )
    return int(result.rowcount or 0)


async def revoke_organization_sessions(
    db: AsyncSession, organization_id: UUID, reason: str = "organization_disabled"
) -> int:
    user_ids = select(User.id).where(User.organization_id == organization_id)
    now = datetime.now(UTC)
    result = await db.execute(
        update(UserSession)
        .where(UserSession.user_id.in_(user_ids), UserSession.is_active.is_(True))
        .values(is_active=False, revoked_at=now, revocation_reason=reason)
    )
    return int(result.rowcount or 0)


async def revoke_school_sessions(
    db: AsyncSession, school_id: UUID, reason: str = "school_disabled"
) -> int:
    user_ids = select(User.id).where(User.school_id == school_id)
    now = datetime.now(UTC)
    result = await db.execute(
        update(UserSession)
        .where(UserSession.user_id.in_(user_ids), UserSession.is_active.is_(True))
        .values(is_active=False, revoked_at=now, revocation_reason=reason)
    )
    return int(result.rowcount or 0)
