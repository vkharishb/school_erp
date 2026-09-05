from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import ensure_license_valid, require_permissions
from app.db.session import get_db
from app.models.academic import AcademicClass, Section, Student, StudentEnrollment, Subject
from app.models.attendance import StudentAttendance
from app.models.erp_access import ParentStudentLink, StudentERPAccess
from app.models.fee import Payment, PaymentAllocation, StudentCharge
from app.models.marks import StudentMark
from app.models.organization import AcademicYear
from app.models.school import SchoolConfiguration
from app.models.user import User
from app.schemas.erp_access import LinkedStudentOut, ParentStudentPortalSummary

router = APIRouter(prefix="/parent-student", tags=["Parent / Student Portal"])


def _check_account(user: User) -> None:
    if user.account_type != "PARENT_STUDENT":
        raise HTTPException(status_code=403, detail="Parent / Student account required")


async def _linked(db: AsyncSession, user: User, student_id: UUID | None = None) -> list[UUID]:
    query = select(ParentStudentLink.student_id).where(ParentStudentLink.user_id == user.id)
    if student_id:
        query = query.where(ParentStudentLink.student_id == student_id)
    return list((await db.execute(query)).scalars().all())


@router.get("/me/students", response_model=list[LinkedStudentOut])
async def linked_students(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("parent_student.portal.view"))],
):
    _check_account(user)
    ids = await _linked(db, user)
    if not ids:
        return []
    rows = await db.execute(
        select(Student).where(Student.id.in_(ids)).order_by(Student.first_name, Student.last_name)
    )
    return [
        LinkedStudentOut(
            id=s.id,
            school_id=s.school_id,
            student_code=s.student_code,
            admission_number=s.admission_number,
            display_name=" ".join(
                part for part in (s.first_name, s.middle_name, s.last_name) if part
            ),
            status=s.status,
        )
        for s in rows.scalars().all()
    ]


@router.get("/students/{student_id}/summary", response_model=ParentStudentPortalSummary)
async def student_summary(
    student_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_permissions("parent_student.portal.view"))],
):
    _check_account(user)
    if not await _linked(db, user, student_id):
        raise HTTPException(status_code=403, detail="This Student is not linked to your account")
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    await ensure_license_valid(student.school_id, db, "student")

    access_result = await db.execute(
        select(StudentERPAccess)
        .where(
            StudentERPAccess.student_id == student.id,
            StudentERPAccess.status == "ACTIVE",
        )
        .order_by(StudentERPAccess.opted_at.desc())
    )
    if not access_result.scalars().first():
        raise HTTPException(status_code=403, detail="ERP access is not active for this Student")

    school_config = (
        await db.execute(
            select(SchoolConfiguration).where(SchoolConfiguration.school_id == student.school_id)
        )
    ).scalar_one_or_none()

    enrollment_result = await db.execute(
        select(StudentEnrollment, AcademicYear, AcademicClass, Section)
        .join(AcademicYear, AcademicYear.id == StudentEnrollment.academic_year_id)
        .join(AcademicClass, AcademicClass.id == StudentEnrollment.academic_class_id)
        .join(Section, Section.id == StudentEnrollment.section_id)
        .where(StudentEnrollment.student_id == student.id, StudentEnrollment.status == "active")
        .order_by(AcademicYear.starts_on.desc())
    )
    enrollment_row = enrollment_result.first()
    enrollment = None
    current_academic_year_id = None
    if enrollment_row:
        e, ay, cls, sec = enrollment_row
        current_academic_year_id = ay.id
        enrollment = {
            "academic_year": ay.name,
            "academic_year_code": ay.code,
            "class": cls.name,
            "section": sec.name,
            "roll_number": e.roll_number,
        }

    attendance_rows = await db.execute(
        select(StudentAttendance.status, func.count(StudentAttendance.id))
        .where(StudentAttendance.student_id == student.id)
        .group_by(StudentAttendance.status)
    )
    attendance_counts = {status: int(count) for status, count in attendance_rows.all()}
    attendance_total = sum(attendance_counts.values())

    mark_query = (
        select(StudentMark, Subject)
        .join(Subject, Subject.id == StudentMark.subject_id)
        .where(StudentMark.student_id == student.id, StudentMark.is_locked.is_(True))
        .order_by(StudentMark.assessment_name, Subject.name)
    )
    if current_academic_year_id:
        mark_query = mark_query.where(StudentMark.academic_year_id == current_academic_year_id)
    marks_result = await db.execute(mark_query)
    marks = [
        {
            "subject": subject.name,
            "assessment": mark.assessment_name,
            "max_marks": str(mark.max_marks),
            "marks_obtained": str(mark.marks_obtained),
            "remarks": mark.remarks,
        }
        for mark, subject in marks_result.all()
    ]

    charge_query = select(StudentCharge).where(StudentCharge.student_id == student.id)
    if current_academic_year_id:
        charge_query = charge_query.where(
            StudentCharge.academic_year_id == current_academic_year_id
        )
    charges = list(
        (await db.execute(charge_query.order_by(StudentCharge.created_at))).scalars().all()
    )
    charge_ids = [c.id for c in charges]
    paid_map: dict[UUID, Decimal] = {}
    if charge_ids:
        paid_rows = await db.execute(
            select(
                PaymentAllocation.charge_id, func.coalesce(func.sum(PaymentAllocation.amount), 0)
            )
            .join(Payment, Payment.id == PaymentAllocation.payment_id)
            .where(PaymentAllocation.charge_id.in_(charge_ids), Payment.status == "posted")
            .group_by(PaymentAllocation.charge_id)
        )
        paid_map = {charge_id: Decimal(str(amount or 0)) for charge_id, amount in paid_rows.all()}
    fee_items = []
    total = Decimal("0")
    paid = Decimal("0")
    for charge in charges:
        amount = Decimal(str(charge.amount))
        paid_amount = paid_map.get(charge.id, Decimal("0"))
        total += amount
        paid += paid_amount
        fee_items.append(
            {
                "description": charge.description,
                "amount": str(amount),
                "paid": str(paid_amount),
                "due": str(max(amount - paid_amount, Decimal("0"))),
                "status": charge.status,
            }
        )

    return ParentStudentPortalSummary(
        student={
            "id": str(student.id),
            "student_code": student.student_code,
            "admission_number": student.admission_number,
            "name": " ".join(
                part
                for part in (student.first_name, student.middle_name, student.last_name)
                if part
            ),
            "date_of_birth": student.date_of_birth.isoformat() if student.date_of_birth else None,
            "gender": student.gender,
            "school_name": school_config.name if school_config else None,
            "status": student.status,
        },
        enrollment=enrollment,
        attendance={"total": attendance_total, **attendance_counts},
        marks=marks,
        fees={
            "total": str(total),
            "paid": str(paid),
            "due": str(max(total - paid, Decimal("0"))),
            "items": fee_items,
        },
    )
