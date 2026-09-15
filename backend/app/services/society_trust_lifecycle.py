import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.academic import Guardian, Student, StudentEnrollment, StudentGuardian
from app.models.attendance import StudentAttendance, TeacherAttendance
from app.models.erp_access import ERPAccessPolicy, ParentStudentLink, StudentERPAccess
from app.models.fee import (
    FeeHead,
    FeeStructureItem,
    Payment,
    PaymentAllocation,
    ReceiptSequence,
    StudentCharge,
)
from app.models.license import SchoolLicense
from app.models.marks import StudentMark
from app.models.organization import AcademicYear, Campus, Organization
from app.models.school import School
from app.models.staff import Teacher
from app.models.subscription import OrganizationSubscription
from app.models.user import User
from app.services.transactional_email import send_transactional_email

logger = logging.getLogger(__name__)


async def _purge_operational_school_data(db, organization_id) -> None:
    """Delete operational tenant data while preserving School/basic commercial history.

    School, SchoolConfiguration, UDISE, SchoolSubscription, activation-key and
    Organization payment records are intentionally retained. Child operational
    rows are removed in reverse dependency order so RESTRICT foreign keys do not
    make the retention worker crash in production.
    """
    school_ids = select(School.id).where(School.organization_id == organization_id)
    campus_ids = select(Campus.id).where(Campus.school_id.in_(school_ids))
    student_ids = select(Student.id).where(Student.school_id.in_(school_ids))
    teacher_ids = select(Teacher.id).where(Teacher.school_id.in_(school_ids))
    payment_ids = select(Payment.id).where(Payment.school_id.in_(school_ids))
    charge_ids = select(StudentCharge.id).where(StudentCharge.school_id.in_(school_ids))
    guardian_ids = select(Guardian.id).where(Guardian.school_id.in_(school_ids))

    # Deep children first.
    await db.execute(
        delete(PaymentAllocation).where(
            (PaymentAllocation.payment_id.in_(payment_ids))
            | (PaymentAllocation.student_charge_id.in_(charge_ids))
        )
    )
    await db.execute(delete(ParentStudentLink).where(ParentStudentLink.student_id.in_(student_ids)))
    await db.execute(delete(StudentERPAccess).where(StudentERPAccess.student_id.in_(student_ids)))
    await db.execute(delete(StudentMark).where(StudentMark.school_id.in_(school_ids)))
    await db.execute(delete(StudentAttendance).where(StudentAttendance.school_id.in_(school_ids)))
    await db.execute(delete(TeacherAttendance).where(TeacherAttendance.school_id.in_(school_ids)))
    await db.execute(delete(StudentEnrollment).where(StudentEnrollment.student_id.in_(student_ids)))
    await db.execute(delete(StudentGuardian).where(
        StudentGuardian.student_id.in_(student_ids) | StudentGuardian.guardian_id.in_(guardian_ids)
    ))

    # Finance operational ledger (commercial Organization subscription payments
    # live in a different table and are deliberately retained).
    await db.execute(delete(Payment).where(Payment.school_id.in_(school_ids)))
    await db.execute(delete(StudentCharge).where(StudentCharge.school_id.in_(school_ids)))
    await db.execute(delete(FeeStructureItem).where(FeeStructureItem.school_id.in_(school_ids)))
    await db.execute(delete(ReceiptSequence).where(ReceiptSequence.school_id.in_(school_ids)))
    await db.execute(delete(ERPAccessPolicy).where(ERPAccessPolicy.school_id.in_(school_ids)))
    await db.execute(delete(FeeHead).where(FeeHead.school_id.in_(school_ids)))

    # People and school-scoped identities.
    await db.execute(delete(Teacher).where(Teacher.school_id.in_(school_ids)))
    await db.execute(delete(Student).where(Student.school_id.in_(school_ids)))
    await db.execute(delete(Guardian).where(Guardian.school_id.in_(school_ids)))
    # Preserve account/audit identity references but make all School-scoped
    # accounts unusable after operational retention purge.
    await db.execute(
        update(User)
        .where(User.school_id.in_(school_ids))
        .values(is_active=False, campus_id=None)
    )

    # Academic projections/configuration are operational and can be rebuilt if
    # a retained School is ever re-onboarded under a future commercial contract.
    await db.execute(delete(AcademicYear).where(AcademicYear.campus_id.in_(campus_ids)))
    # AcademicClass/Section/Subject rows cascade from Campus; deleting the
    # internal MAIN compatibility scope is now safe after dependent rows above.
    await db.execute(delete(Campus).where(Campus.school_id.in_(school_ids)))

    # License is operational access state, not retained commercial history.
    await db.execute(delete(SchoolLicense).where(SchoolLicense.school_id.in_(school_ids)))

    # Retained School records must never appear operational after purge.
    await db.execute(
        update(School)
        .where(School.id.in_(school_ids))
        .values(is_active=False)
    )


async def enforce_society_trust_retention() -> None:
    """Inform Platform Owner before deleting operational data at 6 months.

    Failures are isolated per Society/Trust so one malformed tenant cannot stop
    retention processing for every other tenant or crash the hourly worker.
    """
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        orgs = list(
            (
                await db.execute(
                    select(Organization).where(
                        Organization.archived_at.is_not(None),
                        Organization.operational_data_deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        for org in orgs:
            try:
                sub = (
                    await db.execute(
                        select(OrganizationSubscription)
                        .where(OrganizationSubscription.organization_id == org.id)
                        .order_by(OrganizationSubscription.created_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if not sub:
                    continue
                delete_at = sub.expires_at + timedelta(days=180)
                if (
                    now >= delete_at - timedelta(days=30)
                    and org.deletion_information_sent_at is None
                ):
                    send_transactional_email(
                        to_email=get_settings().super_admin_email,
                        subject="Society/Trust operational data deletion information",
                        body=(
                            f"{org.name} ({org.code}) operational data is scheduled for deletion "
                            f"on {delete_at.date().isoformat()} under the expired-subscription retention policy. "
                            "Society/Trust basic information, School identity, subscription details and "
                            "Organization payment details are retained."
                        ),
                    )
                    org.deletion_information_sent_at = now
                if now >= delete_at:
                    await _purge_operational_school_data(db, org.id)
                    org.operational_data_deleted_at = now
                await db.commit()
            except Exception:
                await db.rollback()
                logger.exception(
                    "Operational retention failed for organization %s; continuing with remaining tenants",
                    org.id,
                )
