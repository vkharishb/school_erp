from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    ensure_campus_access,
    ensure_license_valid,
    ensure_school_access,
    get_role_codes,
    require_permissions,
)
from app.db.session import get_db
from app.models.staff import Teacher
from app.models.user import User
from app.schemas.teacher import TeacherCreate, TeacherOut, TeacherUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/teachers", tags=["Teachers Management"])


@router.get("/{school_id}", response_model=list[TeacherOut])
async def list_teachers(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("teacher.view"))],
    search: str | None = None,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0,
):
    await ensure_school_access(user, db, school_id)
    await ensure_license_valid(school_id, db, "teacher")
    query = select(Teacher).where(Teacher.school_id == school_id)
    if (
        user.campus_id
        and "ORGANIZATION_ADMIN" not in get_role_codes(user)
        and not user.is_superuser
    ):
        query = query.where(Teacher.campus_id == user.campus_id)
    if active_only:
        query = query.where(Teacher.is_active.is_(True))
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Teacher.first_name.ilike(term),
                Teacher.last_name.ilike(term),
                Teacher.employee_code.ilike(term),
                Teacher.email.ilike(term),
            )
        )
    result = await db.execute(
        query.order_by(Teacher.first_name, Teacher.last_name).offset(offset).limit(min(limit, 500))
    )
    return list(result.scalars().all())


@router.post("/{school_id}", response_model=TeacherOut, status_code=201)
async def create_teacher(
    school_id: UUID,
    payload: TeacherCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("teacher.create"))],
):
    await ensure_school_access(user, db, school_id)
    await ensure_license_valid(school_id, db, "teacher")
    campus = await ensure_campus_access(user, db, payload.campus_id)
    if campus.school_id != school_id:
        raise HTTPException(status_code=422, detail="Campus does not belong to this school")
    exists = await db.execute(
        select(Teacher).where(
            Teacher.school_id == school_id, Teacher.employee_code == payload.employee_code
        )
    )
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Employee code already exists")
    teacher = Teacher(school_id=school_id, **payload.model_dump())
    db.add(teacher)
    await db.flush()
    await record_audit(
        db,
        action="teacher.created",
        user=user,
        module="teacher",
        entity_type="Teacher",
        entity_id=teacher.id,
        after={"employee_code": teacher.employee_code, "name": teacher.first_name},
        request=request,
    )
    return teacher


@router.patch("/{teacher_id}", response_model=TeacherOut)
async def update_teacher(
    teacher_id: UUID,
    payload: TeacherUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("teacher.edit"))],
):
    teacher = await db.get(Teacher, teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    await ensure_school_access(user, db, teacher.school_id)
    await ensure_license_valid(teacher.school_id, db, "teacher")
    await ensure_campus_access(user, db, teacher.campus_id)
    before = {
        "first_name": teacher.first_name,
        "last_name": teacher.last_name,
        "status": teacher.status,
        "is_active": teacher.is_active,
    }
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(teacher, field, value)
    await db.flush()
    await record_audit(
        db,
        action="teacher.updated",
        user=user,
        module="teacher",
        entity_type="Teacher",
        entity_id=teacher.id,
        before=before,
        after=payload.model_dump(exclude_unset=True),
        request=request,
    )
    return teacher
