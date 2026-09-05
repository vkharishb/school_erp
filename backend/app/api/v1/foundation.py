from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    ensure_campus_access,
    ensure_school_access,
    get_current_user,
    require_permissions,
)
from app.db.session import get_db
from app.models.license import SchoolLicense
from app.models.organization import AcademicYear, Campus
from app.models.user import User
from app.schemas.foundation import (
    AcademicYearCreate,
    AcademicYearOut,
    ActivationOut,
    CampusCreate,
    CampusOut,
)

router = APIRouter(prefix="/foundation", tags=["Platform Foundation"])


@router.post(
    "/schools/{school_id}/campuses", response_model=CampusOut, status_code=status.HTTP_201_CREATED
)
async def create_campus(
    school_id: UUID,
    payload: CampusCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("school.admin.edit"))],
):
    await ensure_school_access(current_user, db, school_id)
    exists = await db.execute(
        select(Campus).where(Campus.school_id == school_id, Campus.code == payload.code)
    )
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Campus code already exists")
    license_result = await db.execute(
        select(SchoolLicense).where(SchoolLicense.school_id == school_id)
    )
    school_license = license_result.scalar_one_or_none()

    campus = Campus(
        school_id=school_id,
        enabled_modules=list(school_license.enabled_modules or []) if school_license else [],
        license_starts_at=school_license.starts_at if school_license else None,
        license_expires_at=school_license.expires_at if school_license else None,
        **payload.model_dump(),
    )
    db.add(campus)
    await db.flush()
    return campus


@router.get("/schools/{school_id}/campuses", response_model=list[CampusOut])
async def list_campuses(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await ensure_school_access(current_user, db, school_id)
    query = select(Campus).where(Campus.school_id == school_id, Campus.is_active.is_(True))
    if not current_user.is_superuser and current_user.account_type not in {
        "ORGANIZATION_ADMIN",
        "SCHOOL_ADMIN",
    }:
        if not current_user.campus_id:
            raise HTTPException(status_code=403, detail="Campus scope is not assigned")
        query = query.where(Campus.id == current_user.campus_id)
    result = await db.execute(query.order_by(Campus.name))
    return list(result.scalars().all())


@router.post(
    "/campuses/{campus_id}/academic-years",
    response_model=AcademicYearOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_academic_year(
    campus_id: UUID,
    payload: AcademicYearCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("academic_year.manage"))],
):
    # Academic-year dates are an organization-wide invariant in this ERP.
    # Keeping a campus-specific write API would allow a client to bypass
    # synchronization across branches, so writes must use the organization API.
    await ensure_campus_access(current_user, db, campus_id)
    raise HTTPException(
        status_code=409,
        detail="Academic years are organization-wide. Use the organization Academic Years screen/API.",
    )


@router.get("/campuses/{campus_id}/academic-years", response_model=list[AcademicYearOut])
async def list_academic_years(
    campus_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    await ensure_campus_access(current_user, db, campus_id)
    result = await db.execute(
        select(AcademicYear)
        .where(AcademicYear.campus_id == campus_id)
        .order_by(AcademicYear.starts_on.desc())
    )
    return list(result.scalars().all())


@router.post("/academic-years/{academic_year_id}/activate", response_model=ActivationOut)
async def activate_academic_year(
    academic_year_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_permissions("academic_year.manage"))],
):
    year = await db.get(AcademicYear, academic_year_id)
    if not year:
        raise HTTPException(status_code=404, detail="Academic year not found")
    await ensure_campus_access(current_user, db, year.campus_id)
    raise HTTPException(
        status_code=409,
        detail="Academic-year activation is organization-wide. Use the organization Academic Years screen/API.",
    )
