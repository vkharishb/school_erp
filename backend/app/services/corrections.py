from uuid import UUID

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.governance import AnnualCorrectionUsage
from app.models.organization import OrganizationAcademicYear
from app.models.user import User


def change_reason(request: Request) -> str:
    reason = (request.headers.get("X-Change-Reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=422, detail="Reason is required for this change")
    return reason


async def active_organization_year(
    db: AsyncSession, organization_id: UUID
) -> OrganizationAcademicYear:
    result = await db.execute(
        select(OrganizationAcademicYear)
        .where(
            OrganizationAcademicYear.organization_id == organization_id,
            OrganizationAcademicYear.status == "active",
        )
        .order_by(OrganizationAcademicYear.starts_on.desc())
    )
    year = result.scalars().first()
    if not year:
        raise HTTPException(
            status_code=409,
            detail="Activate the Organization Academic Year before using the annual correction.",
        )
    return year


async def consume_annual_correction(
    db: AsyncSession,
    request: Request,
    actor: User,
    *,
    organization_id: UUID,
    entity_type: str,
    entity_id: UUID,
    school_id: UUID | None = None,
) -> AnnualCorrectionUsage | None:
    """Consume the one client correction for the active academic year.

    Super Admin is intentionally unlimited and therefore does not consume a slot.
    """
    if actor.is_superuser:
        return None
    year = await active_organization_year(db, organization_id)
    existing = await db.execute(
        select(AnnualCorrectionUsage).where(
            AnnualCorrectionUsage.entity_type == entity_type,
            AnnualCorrectionUsage.entity_id == entity_id,
            AnnualCorrectionUsage.organization_academic_year_id == year.id,
        )
    )
    if existing.scalar_one_or_none():
        label = "Organization" if entity_type == "organization" else "School / Branch"
        raise HTTPException(
            status_code=409,
            detail=f"{label} correction for {year.code} has already been used. Contact Super Admin for an override.",
        )
    usage = AnnualCorrectionUsage(
        organization_id=organization_id,
        school_id=school_id,
        organization_academic_year_id=year.id,
        entity_type=entity_type,
        entity_id=entity_id,
        used_by=actor.id,
        reason=change_reason(request),
    )
    db.add(usage)
    await db.flush()
    return usage
