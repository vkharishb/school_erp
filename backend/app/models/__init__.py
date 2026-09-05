# Every ORM model in the app MUST be imported here, exactly once, so that any
# entrypoint (API server, alembic migrations, bootstrap.py, tests, a shell)
# gets the complete SQLAlchemy declarative registry regardless of which other
# modules it happens to import. Relying on incidental imports elsewhere (e.g.
# only via API routers) is what caused repeated "InvalidRequestError: ...
# failed to locate a name" mapper-configuration crashes in different
# entrypoints. This file is the single source of truth going forward.

from app.models.academic import (
    AcademicClass,
    Guardian,
    Section,
    Student,
    StudentEnrollment,
    StudentGuardian,
    Subject,
)
from app.models.approval import ApprovalRequest
from app.models.attendance import StudentAttendance, TeacherAttendance
from app.models.audit import AuditEvent
from app.models.erp_access import ERPAccessPolicy, ParentStudentLink, StudentERPAccess
from app.models.fee import (
    FeeHead,
    FeeStructureItem,
    Payment,
    PaymentAllocation,
    ReceiptSequence,
    StudentCharge,
)
from app.models.governance import AnnualCorrectionUsage, SchoolCodeRegistry
from app.models.license import ModuleDefinition, SchoolLicense
from app.models.marks import StudentMark
from app.models.organization import AcademicYear, Campus, Organization, OrganizationAcademicYear
from app.models.school import School, SchoolConfiguration, SchoolUDISECode
from app.models.session import UserSession
from app.models.staff import Teacher
from app.models.user import Permission, Role, RolePermission, User, UserRole

__all__ = [
    "AcademicClass",
    "AcademicYear",
    "AnnualCorrectionUsage",
    "ApprovalRequest",
    "AuditEvent",
    "Campus",
    "ERPAccessPolicy",
    "FeeHead",
    "FeeStructureItem",
    "Guardian",
    "ModuleDefinition",
    "Organization",
    "OrganizationAcademicYear",
    "ParentStudentLink",
    "Payment",
    "PaymentAllocation",
    "Permission",
    "ReceiptSequence",
    "Role",
    "RolePermission",
    "School",
    "SchoolCodeRegistry",
    "SchoolConfiguration",
    "SchoolLicense",
    "SchoolUDISECode",
    "Section",
    "Student",
    "StudentAttendance",
    "StudentCharge",
    "StudentERPAccess",
    "StudentEnrollment",
    "StudentGuardian",
    "StudentMark",
    "Subject",
    "Teacher",
    "TeacherAttendance",
    "User",
    "UserRole",
    "UserSession",
]
