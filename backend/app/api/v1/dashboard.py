from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    ensure_license_valid,
    ensure_school_access,
    has_permission,
    require_permissions,
)
from app.db.session import get_db
from app.models.academic import Student
from app.models.attendance import StudentAttendance, TeacherAttendance
from app.models.fee import Payment, StudentCharge
from app.models.organization import Organization, OrganizationAcademicYear
from app.models.school import School, SchoolConfiguration
from app.models.staff import Teacher
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/schools/{school_id}/summary")
async def school_dashboard_summary(
    school_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("dashboard.view"))],
):
    await ensure_school_access(user, db, school_id)
    await ensure_license_valid(school_id, db, "dashboard")

    student_filters = [Student.school_id == school_id]
    teacher_filters = [Teacher.school_id == school_id]
    student_attendance_filters = [
        StudentAttendance.school_id == school_id,
        StudentAttendance.attendance_date == date.today(),
        StudentAttendance.status == "present",
    ]
    teacher_attendance_filters = [
        TeacherAttendance.school_id == school_id,
        TeacherAttendance.attendance_date == date.today(),
        TeacherAttendance.status == "present",
    ]
    if user.campus_id:
        student_filters.append(Student.campus_id == user.campus_id)
        teacher_filters.append(Teacher.campus_id == user.campus_id)
        student_attendance_filters.append(StudentAttendance.campus_id == user.campus_id)
        teacher_attendance_filters.append(TeacherAttendance.campus_id == user.campus_id)

    students = (
        await db.execute(
            select(func.count())
            .select_from(Student)
            .where(*student_filters, Student.status == "active")
        )
    ).scalar_one()
    teachers = (
        await db.execute(
            select(func.count())
            .select_from(Teacher)
            .where(*teacher_filters, Teacher.is_active.is_(True))
        )
    ).scalar_one()
    present_students = (
        await db.execute(
            select(func.count()).select_from(StudentAttendance).where(*student_attendance_filters)
        )
    ).scalar_one()
    present_teachers = (
        await db.execute(
            select(func.count()).select_from(TeacherAttendance).where(*teacher_attendance_filters)
        )
    ).scalar_one()

    today = date.today()
    birthday_rows = (
        await db.execute(
            select(Student.id, Student.first_name, Student.last_name, Student.date_of_birth)
            .where(
                *student_filters,
                Student.status == "active",
                Student.date_of_birth.is_not(None),
                extract("month", Student.date_of_birth) == today.month,
                extract("day", Student.date_of_birth) == today.day,
            )
            .order_by(Student.first_name.asc(), Student.last_name.asc())
            .limit(20)
        )
    ).all()
    birthdays_today = [
        {
            "student_id": str(row.id),
            "name": " ".join(part for part in [row.first_name, row.last_name] if part).strip(),
            "age": today.year - row.date_of_birth.year
            if row.date_of_birth
            and (today.month, today.day) >= (row.date_of_birth.month, row.date_of_birth.day)
            else (today.year - row.date_of_birth.year - 1 if row.date_of_birth else None),
        }
        for row in birthday_rows
    ]

    fees_due = None
    fees_collected = None
    if has_permission(user, "fee.view"):
        try:
            await ensure_license_valid(school_id, db, "fee")
            charge_query = (
                select(func.coalesce(func.sum(StudentCharge.amount), 0))
                .select_from(StudentCharge)
                .join(Student, Student.id == StudentCharge.student_id)
                .where(
                    StudentCharge.school_id == school_id,
                    StudentCharge.status.in_(["open", "pending", "partially_paid"]),
                )
            )
            payment_query = select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.school_id == school_id, Payment.status == "posted"
            )
            if user.campus_id:
                charge_query = charge_query.where(Student.campus_id == user.campus_id)
                payment_query = payment_query.where(Payment.campus_id == user.campus_id)
            fees_due = str((await db.execute(charge_query)).scalar_one())
            fees_collected = str((await db.execute(payment_query)).scalar_one())
        except Exception as exc:
            # A disabled Fee module must not break the rest of a permitted dashboard.
            from fastapi import HTTPException

            if not isinstance(exc, HTTPException):
                raise

    school = await db.get(School, school_id)
    school_config = (
        await db.execute(
            select(SchoolConfiguration).where(SchoolConfiguration.school_id == school_id)
        )
    ).scalar_one_or_none()
    organization = (
        await db.get(Organization, school.organization_id)
        if school and school.organization_id
        else None
    )
    active_year = None
    if organization:
        active_year = (
            (
                await db.execute(
                    select(OrganizationAcademicYear)
                    .where(
                        OrganizationAcademicYear.organization_id == organization.id,
                        OrganizationAcademicYear.status == "active",
                    )
                    .order_by(OrganizationAcademicYear.starts_on.desc())
                )
            )
            .scalars()
            .first()
        )

    reminders: list[dict[str, str]] = []
    if active_year is None:
        reminders.append(
            {"type": "academic_year", "message": "No active Academic Year is configured."}
        )
    if fees_due is not None:
        try:
            due_amount = float(fees_due)
        except (TypeError, ValueError):
            due_amount = 0
        if due_amount > 0:
            reminders.append(
                {
                    "type": "fees",
                    "message": f"Outstanding fee dues: ₹{due_amount:,.2f}",
                }
            )

    role = "SUPER_ADMIN" if user.is_superuser else user.account_type
    return {
        "school_id": str(school_id),
        "school_code": school.code if school else None,
        "school_name": school_config.name if school_config else (school.code if school else None),
        "organization_id": str(organization.id) if organization else None,
        "organization_name": organization.name if organization else None,
        "academic_year": active_year.name if active_year else None,
        "academic_year_code": active_year.code if active_year else None,
        "role": role,
        "students": students,
        "teachers": teachers,
        "present_students_today": present_students,
        "present_teachers_today": present_teachers,
        "fees_due": fees_due,
        "fees_collected": fees_collected,
        "birthdays_today": birthdays_today,
        "reminders": reminders,
    }
