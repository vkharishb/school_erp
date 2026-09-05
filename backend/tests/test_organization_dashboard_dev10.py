from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import Student, Subject
from app.models.attendance import StudentAttendance, TeacherAttendance
from app.models.fee import FeeHead, Payment, PaymentAllocation, StudentCharge
from app.models.marks import StudentMark
from app.models.organization import AcademicYear, Campus
from app.models.staff import Teacher
from app.models.user import User
from tests.factories import create_org, create_school, suffix


@pytest.mark.asyncio
async def test_organization_dashboard_calculates_daily_operational_metrics(
    client: AsyncClient,
    admin_headers: dict[str, str],
    db_session: AsyncSession,
):
    token = suffix()
    organization = await create_org(client, admin_headers, token=token)
    school = await create_school(client, admin_headers, organization["id"])
    school_id = UUID(school["id"])
    campus = (
        await db_session.execute(select(Campus).where(Campus.school_id == school_id))
    ).scalar_one()
    platform_owner = (
        (await db_session.execute(select(User).where(User.is_superuser.is_(True))))
        .scalars()
        .first()
    )
    assert platform_owner is not None

    academic_year = AcademicYear(
        campus_id=campus.id,
        code=f"D{token[:6]}",
        name="Dashboard Test Year",
        starts_on=date.today() - timedelta(days=30),
        ends_on=date.today() + timedelta(days=300),
    )
    fee_head = FeeHead(school_id=school_id, code=f"F{token[:6]}", name="Tuition")
    subject = Subject(campus_id=campus.id, code=f"S{token[:6]}", name="Mathematics")
    students = [
        Student(
            school_id=school_id,
            campus_id=campus.id,
            student_code=f"{token}-S1",
            admission_number=f"{token}-A1",
            first_name="Asha",
        ),
        Student(
            school_id=school_id,
            campus_id=campus.id,
            student_code=f"{token}-S2",
            admission_number=f"{token}-A2",
            first_name="Bala",
        ),
    ]
    teachers = [
        Teacher(
            school_id=school_id, campus_id=campus.id, employee_code=f"{token}-T1", first_name="Devi"
        ),
        Teacher(
            school_id=school_id,
            campus_id=campus.id,
            employee_code=f"{token}-T2",
            first_name="Farah",
        ),
    ]
    db_session.add_all([academic_year, fee_head, subject, *students, *teachers])
    await db_session.flush()

    charge = StudentCharge(
        school_id=school_id,
        student_id=students[0].id,
        academic_year_id=academic_year.id,
        fee_head_id=fee_head.id,
        description="September tuition",
        amount=Decimal("1000.00"),
        due_date=date.today() - timedelta(days=1),
        source_type="dashboard_test",
    )
    payment = Payment(
        school_id=school_id,
        student_id=students[0].id,
        campus_id=campus.id,
        amount=Decimal("400.00"),
        payment_mode="cash",
        receipt_number=f"RCPT-{token}",
        status="posted",
        collected_by=platform_owner.id,
        collected_at=datetime.now(UTC),
    )
    db_session.add_all(
        [
            charge,
            payment,
            StudentAttendance(
                school_id=school_id,
                campus_id=campus.id,
                student_id=students[0].id,
                attendance_date=date.today(),
                status="present",
                marked_by=platform_owner.id,
            ),
            StudentAttendance(
                school_id=school_id,
                campus_id=campus.id,
                student_id=students[1].id,
                attendance_date=date.today(),
                status="absent",
                marked_by=platform_owner.id,
            ),
            TeacherAttendance(
                school_id=school_id,
                campus_id=campus.id,
                teacher_id=teachers[0].id,
                attendance_date=date.today(),
                status="present",
                marked_by=platform_owner.id,
            ),
            TeacherAttendance(
                school_id=school_id,
                campus_id=campus.id,
                teacher_id=teachers[1].id,
                attendance_date=date.today(),
                status="leave",
                marked_by=platform_owner.id,
            ),
            StudentMark(
                school_id=school_id,
                campus_id=campus.id,
                academic_year_id=academic_year.id,
                student_id=students[0].id,
                subject_id=subject.id,
                assessment_name="Term 1",
                max_marks=Decimal("100.00"),
                marks_obtained=Decimal("80.00"),
                is_locked=True,
                entered_by=platform_owner.id,
                locked_by=platform_owner.id,
            ),
        ]
    )
    await db_session.flush()
    db_session.add(
        PaymentAllocation(payment_id=payment.id, charge_id=charge.id, amount=Decimal("400.00"))
    )
    await db_session.flush()

    response = await client.get(
        f"/api/v1/organizations/{organization['id']}/dashboard",
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["today_collection"] == "400.00"
    assert body["outstanding_due"] == "600.00"
    assert body["overdue_due"] == "600.00"
    assert (
        body["student_attendance_present"],
        body["student_attendance_marked"],
        body["student_attendance_percentage"],
    ) == (1, 2, 50.0)
    assert (
        body["teacher_attendance_present"],
        body["teacher_attendance_marked"],
        body["teacher_attendance_percentage"],
    ) == (1, 2, 50.0)
    assert body["student_performance_percentage"] == 80.0
    assert body["units"][0]["today_collection"] == "400.00"
