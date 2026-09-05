"""
Bootstrap Super Admin + system roles + module catalog.
Safe to run multiple times (idempotent).
"""

import asyncio
import uuid

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.platform_catalog import PLATFORM_MODULES
from app.core.security import get_password_hash
from app.core.usernames import normalize_username
from app.db.session import AsyncSessionLocal
from app.models.license import ModuleDefinition
from app.models.user import Permission, Role, RolePermission, User, UserRole

settings = get_settings()

# ---------------------------------------------------------------------------
# Module catalog
# ---------------------------------------------------------------------------
MODULES = [
    (item["code"], item["name"], item["is_core"], index * 10 + 10)
    for index, item in enumerate(PLATFORM_MODULES)
]

# ---------------------------------------------------------------------------
# Core permissions (expand as modules grow)
# ---------------------------------------------------------------------------
PERMISSIONS = [
    ("dashboard.view", "View dashboard", "dashboard"),
    ("organization.view", "View organization", "school_admin"),
    ("organization.create", "Create organization", "school_admin"),
    ("organization.edit", "Edit organization", "school_admin"),
    ("organization.status.manage", "Enable/disable organization", "school_admin"),
    ("license.manage", "Manage organization and school licenses", "school_admin"),
    ("module.manage", "Enable/disable licensed modules", "school_admin"),
    ("school.config.view", "View school configuration", "school_admin"),
    ("school.config.edit", "Edit school configuration", "school_admin"),
    ("school.admin.view", "View school administration", "school_admin"),
    ("school.admin.edit", "Edit school administration", "school_admin"),
    ("user.view", "View users", "school_admin"),
    ("user.create", "Create users", "school_admin"),
    ("user.edit", "Edit users", "school_admin"),
    ("role.manage", "Manage roles & permissions", "school_admin"),
    ("license.view", "View license", "school_admin"),
    ("academic_year.view", "View academic years", "school_admin"),
    ("academic_year.manage", "Manage academic years", "school_admin"),
    ("academic_class.manage", "Manage classes & sections", "school_admin"),
    ("academic_class.bulk_upload", "Bulk upload classes", "school_admin"),
    ("section.bulk_upload", "Bulk upload sections", "school_admin"),
    ("subject.manage", "Manage subjects", "school_admin"),
    ("system.settings.manage", "Manage platform system settings", "school_admin"),
    ("student.view", "View students", "student"),
    ("student.create", "Create students", "student"),
    ("student.edit", "Edit students", "student"),
    ("student.bulk_upload", "Bulk upload students", "student"),
    ("teacher.view", "View teachers", "teacher"),
    ("teacher.create", "Create teachers", "teacher"),
    ("teacher.edit", "Edit teachers", "teacher"),
    ("teacher.bulk_upload", "Bulk upload teachers", "teacher"),
    ("fee.view", "View fees", "fee"),
    ("fee.collect", "Collect fees", "fee"),
    ("fee.head.manage", "Manage fee heads", "fee"),
    ("fee.structure.manage", "Manage fee structures", "fee"),
    ("fee.structure.bulk_upload", "Bulk upload fee structures", "fee"),
    ("fee.dues.bulk_upload", "Bulk upload prior-year dues", "fee"),
    ("fee.cancel.request", "Request fee receipt cancellation", "fee"),
    ("fee.cancel.approve", "Approve fee receipt cancellation", "fee"),
    ("fee.export", "Export financial reports", "fee"),
    ("attendance.view", "View attendance", "attendance"),
    ("attendance.mark", "Mark attendance", "attendance"),
    ("marks.view", "View marks", "marks"),
    ("marks.edit", "Enter/edit marks", "marks"),
    ("marks.bulk_upload", "Bulk upload marks", "marks"),
    ("marks.finalize", "Lock/unlock finalized marks", "marks"),
    ("exam.view", "View examinations", "exams"),
    ("exam.manage", "Manage examinations", "exams"),
    ("timetable.view", "View timetable", "timetable"),
    ("timetable.manage", "Manage timetable", "timetable"),
    ("certificate.view", "View certificates", "certificates"),
    ("certificate.issue", "Issue certificates", "certificates"),
    ("reports.view", "View reports", "reports"),
    ("reports.export", "Export reports", "reports"),
    ("approval.decide", "Decide approval requests", "school_admin"),
    ("audit.view", "View audit events", "school_admin"),
    ("erp_access.manage", "Configure annual Parent/Student ERP access fee", "fee"),
    ("erp_access.opt", "Opt a student into Parent/Student ERP access", "student"),
    ("parent_student.portal.view", "View linked Parent/Student portal data", "student"),
]


async def bootstrap() -> None:
    async with AsyncSessionLocal() as db:
        # 1. Modules
        for code, name, is_core, order in MODULES:
            exists = await db.execute(select(ModuleDefinition).where(ModuleDefinition.code == code))
            module = exists.scalar_one_or_none()
            if not module:
                db.add(ModuleDefinition(code=code, name=name, is_core=is_core, sort_order=order))
            else:
                module.name = name
                module.is_core = is_core
                module.sort_order = order

        # 2. Permissions
        perm_map: dict[str, uuid.UUID] = {}
        for code, name, module in PERMISSIONS:
            result = await db.execute(select(Permission).where(Permission.code == code))
            perm = result.scalar_one_or_none()
            if not perm:
                perm = Permission(code=code, name=name, module=module)
                db.add(perm)
                await db.flush()
            perm_map[code] = perm.id

        # 3. System roles (global)
        async def ensure_role(code: str, name: str, perm_codes: list[str]) -> Role:
            result = await db.execute(
                select(Role).where(Role.code == code, Role.school_id.is_(None))
            )
            role = result.scalar_one_or_none()
            if not role:
                role = Role(code=code, name=name, is_system=True, school_id=None)
                db.add(role)
                await db.flush()
            # Predefined system-role permissions are an exact matrix, not an
            # additive bootstrap. Removing stale permissions prevents an older
            # role definition from silently retaining broader access.
            allowed_ids = {perm_map[pc] for pc in perm_codes if pc in perm_map}
            existing_rows = await db.execute(
                select(RolePermission).where(RolePermission.role_id == role.id)
            )
            for row in existing_rows.scalars().all():
                if row.permission_id not in allowed_ids:
                    await db.delete(row)
            await db.flush()
            for pc in perm_codes:
                pid = perm_map.get(pc)
                if not pid:
                    continue
                exists = await db.execute(
                    select(RolePermission).where(
                        RolePermission.role_id == role.id,
                        RolePermission.permission_id == pid,
                    )
                )
                if not exists.scalar_one_or_none():
                    db.add(RolePermission(role_id=role.id, permission_id=pid))
            return role

        super_role = await ensure_role(
            "SUPER_ADMIN",
            "Super Admin / Platform Owner",
            list(perm_map.keys()),
        )
        organization_admin_permissions = [
            "dashboard.view",
            "organization.view",
            "organization.edit",
            "school.config.view",
            "school.config.edit",
            "school.admin.view",
            "school.admin.edit",
            "user.view",
            "user.create",
            "user.edit",
            "license.view",
            "academic_year.view",
            "academic_year.manage",
            "academic_class.manage",
            "academic_class.bulk_upload",
            "section.bulk_upload",
            "subject.manage",
            "student.view",
            "student.create",
            "student.edit",
            "student.bulk_upload",
            "teacher.view",
            "teacher.create",
            "teacher.edit",
            "teacher.bulk_upload",
            "fee.view",
            "fee.collect",
            "fee.head.manage",
            "fee.structure.manage",
            "fee.structure.bulk_upload",
            "fee.dues.bulk_upload",
            "fee.cancel.request",
            "fee.cancel.approve",
            "fee.export",
            "attendance.view",
            "attendance.mark",
            "marks.view",
            "marks.edit",
            "marks.bulk_upload",
            "marks.finalize",
            "reports.view",
            "reports.export",
            "approval.decide",
            "audit.view",
            "erp_access.manage",
            "erp_access.opt",
        ]
        await ensure_role(
            "ORGANIZATION_ADMIN", "Organization Admin", organization_admin_permissions
        )
        await ensure_role(
            "SCHOOL_ADMIN",
            "School / Branch Admin",
            [
                code
                for code in organization_admin_permissions
                if code not in {"organization.edit", "academic_year.manage"}
            ],
        )
        await ensure_role(
            "ACCOUNTS",
            "Accounts",
            [
                "dashboard.view",
                "student.view",
                "fee.view",
                "fee.collect",
                "fee.head.manage",
                "fee.structure.manage",
                "fee.structure.bulk_upload",
                "fee.dues.bulk_upload",
                "fee.cancel.request",
                "fee.export",
                "reports.view",
                "reports.export",
                "erp_access.opt",
            ],
        )
        await ensure_role(
            "TEACHER",
            "Teacher",
            [
                "dashboard.view",
                "student.view",
                "attendance.view",
                "attendance.mark",
                "marks.view",
                "marks.edit",
                "teacher.view",
                "reports.view",
                "erp_access.opt",
            ],
        )
        await ensure_role(
            "RECEPTIONIST",
            "Receptionist",
            ["dashboard.view", "fee.view", "teacher.view"],
        )
        await ensure_role(
            "PARENT_STUDENT",
            "Parent / Student",
            ["dashboard.view", "parent_student.portal.view"],
        )

        # 4. Environment-configured Super Admin user
        super_admin_username = normalize_username(settings.super_admin_username)
        result = await db.execute(
            select(User).where(
                (func.lower(User.username) == super_admin_username)
                | (func.lower(User.email) == settings.super_admin_email.lower())
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                username=super_admin_username,
                email=settings.super_admin_email,
                hashed_password=get_password_hash(settings.super_admin_password),
                full_name=settings.super_admin_full_name,
                is_active=True,
                is_superuser=True,
                account_type="SUPER_ADMIN",
                school_id=None,
            )
            db.add(user)
            print("[bootstrap] Created configured Super Admin")
        else:
            if not getattr(user, "username", None):
                user.username = super_admin_username
            if settings.app_env.lower() in {"test", "ci"}:
                user.hashed_password = get_password_hash(settings.super_admin_password)
                user.is_active = True
                user.is_superuser = True
                user.account_type = "SUPER_ADMIN"
                print(f"[bootstrap] Super Admin test credentials synchronized: {user.username}")
            else:
                print(
                    f"[bootstrap] Super Admin already exists: {user.username} (password unchanged)"
                )

        await db.flush()
        platform_assignment = await db.execute(
            select(UserRole).where(
                UserRole.user_id == user.id,
                UserRole.role_id == super_role.id,
            )
        )
        if not platform_assignment.scalar_one_or_none():
            db.add(UserRole(user_id=user.id, role_id=super_role.id))

        await db.commit()
        print("[bootstrap] Done.")


if __name__ == "__main__":
    asyncio.run(bootstrap())
