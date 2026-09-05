from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import ensure_license_valid, ensure_school_access, require_permissions
from app.db.session import get_db
from app.models.academic import Student
from app.models.attendance import StudentAttendance, TeacherAttendance
from app.models.staff import Teacher
from app.models.user import User
from app.schemas.attendance import (
    ATTENDANCE_STATUSES,
    AttendanceBulkMark,
    StudentAttendanceOut,
    TeacherAttendanceOut,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/attendance", tags=["Attendance"])


def _validate_status(status: str) -> None:
    if status not in ATTENDANCE_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid attendance status: {status}")


@router.get("/{school_id}/students", response_model=list[StudentAttendanceOut])
async def list_student_attendance(
    school_id: UUID,
    attendance_date: date,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("attendance.view"))],
):
    await ensure_school_access(user, db, school_id)
    await ensure_license_valid(school_id, db, "attendance")
    query = select(StudentAttendance).where(
        StudentAttendance.school_id == school_id,
        StudentAttendance.attendance_date == attendance_date,
    )
    if user.campus_id:
        query = query.where(StudentAttendance.campus_id == user.campus_id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.put("/{school_id}/students", response_model=list[StudentAttendanceOut])
async def mark_student_attendance(
    school_id: UUID,
    payload: AttendanceBulkMark,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("attendance.mark"))],
):
    await ensure_school_access(user, db, school_id)
    await ensure_license_valid(school_id, db, "attendance")
    output: list[StudentAttendance] = []
    audit_changes: list[tuple[StudentAttendance, str, dict | None, dict]] = []
    for mark in payload.records:
        _validate_status(mark.status)
        student = await db.get(Student, mark.entity_id)
        if not student or student.school_id != school_id:
            raise HTTPException(status_code=422, detail=f"Invalid student: {mark.entity_id}")
        if user.campus_id and student.campus_id != user.campus_id:
            raise HTTPException(status_code=403, detail="Campus access denied")
        result = await db.execute(
            select(StudentAttendance).where(
                StudentAttendance.student_id == student.id,
                StudentAttendance.attendance_date == payload.attendance_date,
            )
        )
        row = result.scalar_one_or_none()
        before = None
        action = "attendance.student.marked"
        if row:
            before = {
                "status": row.status,
                "remarks": row.remarks,
                "marked_by": str(row.marked_by) if row.marked_by else None,
            }
            action = "attendance.student.corrected"
        else:
            row = StudentAttendance(
                school_id=school_id,
                campus_id=student.campus_id,
                student_id=student.id,
                attendance_date=payload.attendance_date,
                marked_by=user.id,
            )
            db.add(row)
        row.status = mark.status
        row.remarks = mark.remarks
        row.marked_by = user.id
        after = {
            "status": row.status,
            "remarks": row.remarks,
            "marked_by": str(user.id),
            "attendance_date": str(payload.attendance_date),
            "student_id": str(student.id),
        }
        if before is None or before["status"] != row.status or before["remarks"] != row.remarks:
            audit_changes.append((row, action, before, after))
        output.append(row)
    await db.flush()
    for row, action, before, after in audit_changes:
        await record_audit(
            db,
            action=action,
            user=user,
            module="attendance",
            entity_type="StudentAttendance",
            entity_id=row.id,
            before=before,
            after=after,
            request=request,
            target_school_id=school_id,
            target_campus_id=row.campus_id,
        )
    return output


@router.get("/{school_id}/teachers", response_model=list[TeacherAttendanceOut])
async def list_teacher_attendance(
    school_id: UUID,
    attendance_date: date,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("attendance.view"))],
):
    await ensure_school_access(user, db, school_id)
    await ensure_license_valid(school_id, db, "attendance")
    query = select(TeacherAttendance).where(
        TeacherAttendance.school_id == school_id,
        TeacherAttendance.attendance_date == attendance_date,
    )
    if user.campus_id:
        query = query.where(TeacherAttendance.campus_id == user.campus_id)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.put("/{school_id}/teachers", response_model=list[TeacherAttendanceOut])
async def mark_teacher_attendance(
    school_id: UUID,
    payload: AttendanceBulkMark,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("attendance.mark"))],
):
    await ensure_school_access(user, db, school_id)
    await ensure_license_valid(school_id, db, "attendance")
    output: list[TeacherAttendance] = []
    audit_changes: list[tuple[TeacherAttendance, str, dict | None, dict]] = []
    for mark in payload.records:
        _validate_status(mark.status)
        teacher = await db.get(Teacher, mark.entity_id)
        if not teacher or teacher.school_id != school_id:
            raise HTTPException(status_code=422, detail=f"Invalid teacher: {mark.entity_id}")
        if user.campus_id and teacher.campus_id != user.campus_id:
            raise HTTPException(status_code=403, detail="Campus access denied")
        result = await db.execute(
            select(TeacherAttendance).where(
                TeacherAttendance.teacher_id == teacher.id,
                TeacherAttendance.attendance_date == payload.attendance_date,
            )
        )
        row = result.scalar_one_or_none()
        before = None
        action = "attendance.teacher.marked"
        if row:
            before = {
                "status": row.status,
                "remarks": row.remarks,
                "marked_by": str(row.marked_by) if row.marked_by else None,
            }
            action = "attendance.teacher.corrected"
        else:
            row = TeacherAttendance(
                school_id=school_id,
                campus_id=teacher.campus_id,
                teacher_id=teacher.id,
                attendance_date=payload.attendance_date,
                marked_by=user.id,
            )
            db.add(row)
        row.status = mark.status
        row.remarks = mark.remarks
        row.marked_by = user.id
        after = {
            "status": row.status,
            "remarks": row.remarks,
            "marked_by": str(user.id),
            "attendance_date": str(payload.attendance_date),
            "teacher_id": str(teacher.id),
        }
        if before is None or before["status"] != row.status or before["remarks"] != row.remarks:
            audit_changes.append((row, action, before, after))
        output.append(row)
    await db.flush()
    for row, action, before, after in audit_changes:
        await record_audit(
            db,
            action=action,
            user=user,
            module="attendance",
            entity_type="TeacherAttendance",
            entity_id=row.id,
            before=before,
            after=after,
            request=request,
            target_school_id=school_id,
            target_campus_id=row.campus_id,
        )
    return output
