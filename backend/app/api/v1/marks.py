from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    ensure_campus_access,
    ensure_license_valid,
    ensure_school_access,
    get_role_codes,
    require_permissions,
)
from app.db.session import get_db
from app.models.academic import Student, StudentEnrollment, Subject
from app.models.marks import StudentMark
from app.models.organization import AcademicYear
from app.models.user import User
from app.schemas.marks import MarkBulkRequest, MarkLockUpdate, MarkOut, MarkUpsert
from app.services.audit import record_audit

router = APIRouter(prefix="/marks", tags=["Marks"])


async def _validate_refs(db: AsyncSession, school_id: UUID, payload: MarkUpsert):
    student = await db.get(Student, payload.student_id)
    subject = await db.get(Subject, payload.subject_id)
    year = await db.get(AcademicYear, payload.academic_year_id)
    if not student or student.school_id != school_id:
        raise HTTPException(status_code=422, detail="Student does not belong to this school")
    if not subject or subject.campus_id != student.campus_id:
        raise HTTPException(
            status_code=422, detail="Subject does not belong to the student's campus"
        )
    if not year or year.campus_id != student.campus_id:
        raise HTTPException(
            status_code=422, detail="Academic year does not belong to the student's campus"
        )
    if year.is_read_only or year.status == "closed":
        raise HTTPException(status_code=409, detail="Historical academic year is read-only")
    enrollment_result = await db.execute(
        select(StudentEnrollment.id).where(
            StudentEnrollment.student_id == student.id,
            StudentEnrollment.academic_year_id == year.id,
            StudentEnrollment.status == "active",
        )
    )
    if not enrollment_result.scalar_one_or_none():
        raise HTTPException(
            status_code=422, detail="Student is not actively enrolled in the selected academic year"
        )
    return student


@router.get("/{school_id}", response_model=list[MarkOut])
async def list_marks(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("marks.view"))],
    student_id: UUID | None = None,
    subject_id: UUID | None = None,
    academic_year_id: UUID | None = None,
):
    await ensure_school_access(user, db, school_id)
    await ensure_license_valid(school_id, db, "marks")
    query = select(StudentMark).where(StudentMark.school_id == school_id)
    if (
        user.campus_id
        and "ORGANIZATION_ADMIN" not in get_role_codes(user)
        and not user.is_superuser
    ):
        query = query.where(StudentMark.campus_id == user.campus_id)
    if student_id:
        query = query.where(StudentMark.student_id == student_id)
    if subject_id:
        query = query.where(StudentMark.subject_id == subject_id)
    if academic_year_id:
        query = query.where(StudentMark.academic_year_id == academic_year_id)
    result = await db.execute(query.order_by(StudentMark.updated_at.desc()).limit(1000))
    return list(result.scalars().all())


@router.post("/{school_id}", response_model=MarkOut, status_code=201)
async def upsert_mark(
    school_id: UUID,
    payload: MarkUpsert,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("marks.edit"))],
):
    await ensure_school_access(user, db, school_id)
    await ensure_license_valid(school_id, db, "marks")
    student = await _validate_refs(db, school_id, payload)
    await ensure_campus_access(user, db, student.campus_id)
    result = await db.execute(
        select(StudentMark).where(
            StudentMark.school_id == school_id,
            StudentMark.academic_year_id == payload.academic_year_id,
            StudentMark.student_id == payload.student_id,
            StudentMark.subject_id == payload.subject_id,
            StudentMark.assessment_name == payload.assessment_name,
        )
    )
    mark = result.scalar_one_or_none()
    if mark and mark.is_locked:
        raise HTTPException(status_code=409, detail="Marks are locked and cannot be edited")
    before = None
    if mark:
        before = {
            "max_marks": str(mark.max_marks),
            "marks_obtained": str(mark.marks_obtained),
            "remarks": mark.remarks,
        }
        for field, value in payload.model_dump().items():
            setattr(mark, field, value)
    else:
        mark = StudentMark(
            school_id=school_id,
            campus_id=student.campus_id,
            entered_by=user.id,
            **payload.model_dump(),
        )
        db.add(mark)
        await db.flush()
    await record_audit(
        db,
        action="marks.updated" if before else "marks.created",
        user=user,
        module="marks",
        entity_type="StudentMark",
        entity_id=mark.id,
        before=before,
        after={
            "max_marks": str(mark.max_marks),
            "marks_obtained": str(mark.marks_obtained),
            "assessment_name": mark.assessment_name,
        },
        request=request,
    )
    await db.flush()
    return mark


@router.post("/{school_id}/bulk", response_model=list[MarkOut])
async def bulk_upsert_marks(
    school_id: UUID,
    payload: MarkBulkRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("marks.bulk_upload"))],
):
    await ensure_school_access(user, db, school_id)
    await ensure_license_valid(school_id, db, "marks")
    output = []
    for item in payload.records:
        student = await _validate_refs(db, school_id, item)
        await ensure_campus_access(user, db, student.campus_id)
        result = await db.execute(
            select(StudentMark).where(
                StudentMark.school_id == school_id,
                StudentMark.academic_year_id == item.academic_year_id,
                StudentMark.student_id == item.student_id,
                StudentMark.subject_id == item.subject_id,
                StudentMark.assessment_name == item.assessment_name,
            )
        )
        mark = result.scalar_one_or_none()
        if mark and mark.is_locked:
            raise HTTPException(
                status_code=409, detail=f"Locked marks found for student {item.student_id}"
            )
        if mark:
            for field, value in item.model_dump().items():
                setattr(mark, field, value)
        else:
            mark = StudentMark(
                school_id=school_id,
                campus_id=student.campus_id,
                entered_by=user.id,
                **item.model_dump(),
            )
            db.add(mark)
            await db.flush()
        output.append(mark)
    await record_audit(
        db,
        action="marks.bulk_uploaded",
        user=user,
        module="marks",
        entity_type="StudentMark",
        after={"record_count": len(output)},
        request=request,
    )
    await db.flush()
    return output


@router.patch("/{school_id}/{mark_id}/lock", response_model=MarkOut)
async def lock_mark(
    school_id: UUID,
    mark_id: UUID,
    payload: MarkLockUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("marks.finalize"))],
):
    await ensure_school_access(user, db, school_id)
    await ensure_license_valid(school_id, db, "marks")
    mark = await db.get(StudentMark, mark_id)
    if not mark or mark.school_id != school_id:
        raise HTTPException(status_code=404, detail="Mark record not found")
    await ensure_campus_access(user, db, mark.campus_id)
    before = {
        "is_locked": mark.is_locked,
        "locked_by": str(mark.locked_by) if mark.locked_by else None,
        "locked_at": mark.locked_at.isoformat() if mark.locked_at else None,
    }
    if payload.is_locked:
        mark.is_locked = True
        mark.locked_by = user.id
        mark.locked_at = datetime.now(UTC)
        action = "marks.finalized"
        metadata = None
    else:
        # Reopening finalized marks is an administrative correction action, not
        # a normal edit. Require both admin scope and an explicit reason.
        if not mark.is_locked:
            return mark
        if not (user.is_superuser or user.account_type in {"ORGANIZATION_ADMIN", "SCHOOL_ADMIN"}):
            raise HTTPException(
                status_code=403, detail="Only an administrator can reopen finalized marks"
            )
        if not payload.reason or len(payload.reason.strip()) < 3:
            raise HTTPException(
                status_code=422, detail="A reason is required to reopen finalized marks"
            )
        mark.is_locked = False
        mark.locked_by = None
        mark.locked_at = None
        action = "marks.reopened"
        metadata = {"reopen_reason": payload.reason.strip()}
    await record_audit(
        db,
        action=action,
        user=user,
        module="marks",
        entity_type="StudentMark",
        entity_id=mark.id,
        before=before,
        after={
            "is_locked": mark.is_locked,
            "locked_by": str(mark.locked_by) if mark.locked_by else None,
            "locked_at": mark.locked_at.isoformat() if mark.locked_at else None,
        },
        metadata=metadata,
        request=request,
        target_school_id=school_id,
        target_campus_id=mark.campus_id,
    )
    await db.flush()
    return mark
