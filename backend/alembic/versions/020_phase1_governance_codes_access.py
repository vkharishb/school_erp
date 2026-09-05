"""Phase 1 governance, ERP codes, role cleanup and parent/student ERP access.

Revision ID: 020
Revises: 019
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def _global_role_id(bind, code: str):
    return bind.execute(
        sa.text(
            "SELECT id FROM roles WHERE code=:code AND school_id IS NULL ORDER BY created_at LIMIT 1"
        ),
        {"code": code},
    ).scalar_one_or_none()


def _ensure_role(bind, code: str, name: str):
    rid = _global_role_id(bind, code)
    if rid:
        bind.execute(
            sa.text("UPDATE roles SET name=:name, is_system=TRUE WHERE id=:id"),
            {"name": name, "id": rid},
        )
        return rid
    rid = uuid.uuid4()
    bind.execute(
        sa.text(
            "INSERT INTO roles (id, school_id, organization_id, campus_id, code, name, is_system, created_at) "
            "VALUES (:id, NULL, NULL, NULL, :code, :name, TRUE, now())"
        ),
        {"id": rid, "code": code, "name": name},
    )
    return rid


def _ensure_permission(bind, code: str, name: str, module: str):
    pid = bind.execute(
        sa.text("SELECT id FROM permissions WHERE code=:code"), {"code": code}
    ).scalar_one_or_none()
    if pid:
        bind.execute(
            sa.text("UPDATE permissions SET name=:name, module=:module WHERE id=:id"),
            {"name": name, "module": module, "id": pid},
        )
        return pid
    pid = uuid.uuid4()
    bind.execute(
        sa.text(
            "INSERT INTO permissions (id, code, name, module, description) VALUES (:id,:code,:name,:module,NULL)"
        ),
        {"id": pid, "code": code, "name": name, "module": module},
    )
    return pid


def _replace_role_permissions(bind, role_code: str, permission_codes: list[str]):
    rid = _global_role_id(bind, role_code)
    if not rid:
        return
    bind.execute(sa.text("DELETE FROM role_permissions WHERE role_id=:rid"), {"rid": rid})
    if permission_codes == ["*"]:
        pids = list(bind.execute(sa.text("SELECT id FROM permissions")).scalars().all())
    else:
        pids = []
        for code in permission_codes:
            pid = bind.execute(
                sa.text("SELECT id FROM permissions WHERE code=:code"), {"code": code}
            ).scalar_one_or_none()
            if pid:
                pids.append(pid)
    for pid in pids:
        bind.execute(
            sa.text(
                "INSERT INTO role_permissions (id, role_id, permission_id, data_scope) VALUES (:id,:rid,:pid,'{}'::json)"
            ),
            {"id": uuid.uuid4(), "rid": rid, "pid": pid},
        )


def upgrade() -> None:
    # Organization commercial/scope data.
    op.add_column(
        "organizations",
        sa.Column("allowed_schools", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("organizations", sa.Column("head_full_name", sa.String(255), nullable=True))
    op.add_column("organizations", sa.Column("head_email", sa.String(255), nullable=True))
    op.add_column("organizations", sa.Column("head_phone", sa.String(30), nullable=True))

    # Unified school profile fields (same information is entered at creation and edited later).
    for name, coltype in [
        ("area", sa.String(100)),
        ("area_code", sa.String(10)),
        ("tagline", sa.String(255)),
        ("principal_head_name", sa.String(255)),
        ("principal_head_email", sa.String(255)),
        ("principal_head_phone", sa.String(30)),
    ]:
        op.add_column("school_configurations", sa.Column(name, coltype, nullable=True))

    # ERP codes are permanent and scoped to organization. UDISE is optional and one-to-many.
    op.execute("DROP INDEX IF EXISTS ix_schools_code")
    op.execute("DROP INDEX IF EXISTS ix_schools_udise_code")
    # Keep active-school uniqueness for legacy compatibility. A permanent issued-code
    # registry below prevents all future reuse, including after a School is archived.
    op.create_index(
        "ix_schools_org_code",
        "schools",
        ["organization_id", "code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "school_code_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("issued_school_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.UniqueConstraint("organization_id", "code", name="uq_school_code_registry_org_code"),
    )
    op.create_index(
        "ix_school_code_registry_organization_id", "school_code_registry", ["organization_id"]
    )
    bind = op.get_bind()
    issued_codes = bind.execute(
        sa.text(
            "SELECT organization_id, code, "
            "(array_agg(id ORDER BY (deleted_at IS NULL) DESC, created_at DESC))[1] AS school_id "
            "FROM schools WHERE organization_id IS NOT NULL GROUP BY organization_id, code"
        )
    ).all()
    for organization_id, code, school_id in issued_codes:
        bind.execute(
            sa.text(
                "INSERT INTO school_code_registry (id, organization_id, code, issued_school_id, issued_at) "
                "VALUES (:id, :oid, :code, :sid, now())"
            ),
            {"id": uuid.uuid4(), "oid": organization_id, "code": code, "sid": school_id},
        )

    op.create_table(
        "school_udise_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("udise_code", sa.String(50), nullable=False),
        sa.Column("label", sa.String(100), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_school_udise_codes_school_id", "school_udise_codes", ["school_id"])
    op.create_index(
        "ix_school_udise_active_unique",
        "school_udise_codes",
        ["udise_code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND is_active IS TRUE"),
    )
    bind = op.get_bind()
    legacy_udise = bind.execute(
        sa.text(
            "SELECT id, udise_code FROM schools WHERE udise_code IS NOT NULL AND btrim(udise_code) <> ''"
        )
    ).all()
    for school_id, udise_code in legacy_udise:
        exists = bind.execute(
            sa.text("SELECT 1 FROM school_udise_codes WHERE school_id=:sid AND udise_code=:code"),
            {"sid": school_id, "code": udise_code},
        ).scalar_one_or_none()
        if not exists:
            bind.execute(
                sa.text(
                    "INSERT INTO school_udise_codes "
                    "(id, school_id, udise_code, label, is_primary, is_active, created_at, updated_at) "
                    "VALUES (:id, :sid, :code, 'Primary', TRUE, TRUE, now(), now())"
                ),
                {"id": uuid.uuid4(), "sid": school_id, "code": udise_code},
            )

    # User type cleanup: e-mail is contact data, not a login/business key.
    op.execute("DROP INDEX IF EXISTS ix_users_email")
    op.add_column(
        "users", sa.Column("account_type", sa.String(40), nullable=False, server_default="TEACHER")
    )
    op.create_index("ix_users_account_type", "users", ["account_type"])
    op.create_index(
        "ix_parent_student_org_phone_unique",
        "users",
        ["organization_id", "phone"],
        unique=True,
        postgresql_where=sa.text("account_type = 'PARENT_STUDENT' AND phone IS NOT NULL"),
    )
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Annual client correction usage.
    op.create_table(
        "annual_correction_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "organization_academic_year_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization_academic_years.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "used_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "used_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.UniqueConstraint(
            "entity_type",
            "entity_id",
            "organization_academic_year_id",
            name="uq_annual_correction_entity_year",
        ),
    )
    op.create_index(
        "ix_annual_correction_usage_organization_id", "annual_correction_usage", ["organization_id"]
    )
    op.create_index(
        "ix_annual_correction_usage_school_id", "annual_correction_usage", ["school_id"]
    )

    # Parent/Student account -> many linked students.
    op.create_table(
        "parent_student_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("students.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "student_id", name="uq_parent_student_link"),
    )
    op.create_index("ix_parent_student_links_user_id", "parent_student_links", ["user_id"])
    op.create_index("ix_parent_student_links_student_id", "parent_student_links", ["student_id"])

    op.create_table(
        "erp_access_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_academic_year_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization_academic_years.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "fee_head_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fee_heads.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("annual_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "school_id", "organization_academic_year_id", name="uq_erp_access_policy_school_year"
        ),
    )
    op.create_index("ix_erp_access_policies_school_id", "erp_access_policies", ["school_id"])

    op.create_table(
        "student_erp_access",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("students.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_academic_year_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organization_academic_years.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("access_number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column(
            "opted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "opted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "student_id", "organization_academic_year_id", name="uq_student_erp_access_year"
        ),
    )
    op.create_index("ix_student_erp_access_school_id", "student_erp_access", ["school_id"])
    op.create_index("ix_student_erp_access_student_id", "student_erp_access", ["student_id"])
    op.create_index("ix_student_erp_access_access_number", "student_erp_access", ["access_number"])

    op.add_column("student_charges", sa.Column("source_type", sa.String(40), nullable=True))
    op.add_column("student_charges", sa.Column("source_ref", sa.String(100), nullable=True))
    op.create_unique_constraint(
        "uq_student_charge_source_year",
        "student_charges",
        ["student_id", "academic_year_id", "source_type"],
    )

    # Normalize the system role catalog while preserving existing assignments.
    bind = op.get_bind()
    # Simple renames first where no collision exists.
    if _global_role_id(bind, "PLATFORM_SUPER_ADMIN") and not _global_role_id(bind, "SUPER_ADMIN"):
        bind.execute(
            sa.text(
                "UPDATE roles SET code='SUPER_ADMIN', name='Super Admin / Platform Owner' WHERE code='PLATFORM_SUPER_ADMIN' AND school_id IS NULL"
            )
        )
    if _global_role_id(bind, "SCHOOL_ADMIN") and not _global_role_id(bind, "ORGANIZATION_ADMIN"):
        bind.execute(
            sa.text(
                "UPDATE roles SET code='ORGANIZATION_ADMIN', name='Organization Admin' WHERE code='SCHOOL_ADMIN' AND school_id IS NULL"
            )
        )
    if _global_role_id(bind, "ACCOUNTANT") and not _global_role_id(bind, "ACCOUNTS"):
        bind.execute(
            sa.text(
                "UPDATE roles SET code='ACCOUNTS', name='Accounts' WHERE code='ACCOUNTANT' AND school_id IS NULL"
            )
        )
    if _global_role_id(bind, "PARENT") and not _global_role_id(bind, "PARENT_STUDENT"):
        bind.execute(
            sa.text(
                "UPDATE roles SET code='PARENT_STUDENT', name='Parent / Student' WHERE code='PARENT' AND school_id IS NULL"
            )
        )

    _ensure_role(bind, "SUPER_ADMIN", "Super Admin / Platform Owner")
    _ensure_role(bind, "ORGANIZATION_ADMIN", "Organization Admin")
    school_admin_id = _ensure_role(bind, "SCHOOL_ADMIN", "School / Branch Admin")
    # Merge both former school/campus manager labels into the single School Admin role.
    for legacy in ("CAMPUS_ADMIN", "PRINCIPAL"):
        old_id = _global_role_id(bind, legacy)
        if not old_id:
            continue
        perms = (
            bind.execute(
                sa.text("SELECT permission_id FROM role_permissions WHERE role_id=:rid"),
                {"rid": old_id},
            )
            .scalars()
            .all()
        )
        for pid in perms:
            exists = bind.execute(
                sa.text("SELECT 1 FROM role_permissions WHERE role_id=:rid AND permission_id=:pid"),
                {"rid": school_admin_id, "pid": pid},
            ).scalar_one_or_none()
            if not exists:
                bind.execute(
                    sa.text(
                        "INSERT INTO role_permissions (id,role_id,permission_id,data_scope) VALUES (:id,:rid,:pid,'{}'::json)"
                    ),
                    {"id": uuid.uuid4(), "rid": school_admin_id, "pid": pid},
                )
        users = (
            bind.execute(
                sa.text("SELECT user_id FROM user_roles WHERE role_id=:rid"), {"rid": old_id}
            )
            .scalars()
            .all()
        )
        for uid in users:
            exists = bind.execute(
                sa.text("SELECT 1 FROM user_roles WHERE user_id=:uid AND role_id=:rid"),
                {"uid": uid, "rid": school_admin_id},
            ).scalar_one_or_none()
            if not exists:
                bind.execute(
                    sa.text("INSERT INTO user_roles (id,user_id,role_id) VALUES (:id,:uid,:rid)"),
                    {"id": uuid.uuid4(), "uid": uid, "rid": school_admin_id},
                )
        bind.execute(sa.text("DELETE FROM user_roles WHERE role_id=:rid"), {"rid": old_id})
        bind.execute(sa.text("DELETE FROM role_permissions WHERE role_id=:rid"), {"rid": old_id})
        bind.execute(sa.text("DELETE FROM roles WHERE id=:rid"), {"rid": old_id})
    _ensure_role(bind, "ACCOUNTS", "Accounts")
    _ensure_role(bind, "TEACHER", "Teacher")
    _ensure_role(bind, "RECEPTIONIST", "Receptionist")
    _ensure_role(bind, "PARENT_STUDENT", "Parent / Student")

    # Ensure dev.3 permissions exist and lock the predefined role matrix to the
    # approved user types. Custom roles remain Super Admin managed.
    _ensure_permission(
        bind, "erp_access.manage", "Configure annual Parent/Student ERP access fee", "fee"
    )
    _ensure_permission(
        bind, "erp_access.opt", "Opt a student into Parent/Student ERP access", "student"
    )
    _ensure_permission(
        bind, "parent_student.portal.view", "View linked Parent/Student portal data", "student"
    )

    org_admin_perms = [
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
    school_admin_perms = [
        p for p in org_admin_perms if p not in {"organization.edit", "academic_year.manage"}
    ]
    _replace_role_permissions(bind, "SUPER_ADMIN", ["*"])
    _replace_role_permissions(bind, "ORGANIZATION_ADMIN", org_admin_perms)
    _replace_role_permissions(bind, "SCHOOL_ADMIN", school_admin_perms)
    _replace_role_permissions(
        bind,
        "ACCOUNTS",
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
    _replace_role_permissions(
        bind,
        "TEACHER",
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
    _replace_role_permissions(bind, "RECEPTIONIST", ["dashboard.view", "fee.view", "teacher.view"])
    _replace_role_permissions(
        bind, "PARENT_STUDENT", ["dashboard.view", "parent_student.portal.view"]
    )

    # Infer account type from the normalized role assignment.
    bind.execute(sa.text("UPDATE users SET account_type='SUPER_ADMIN' WHERE is_superuser IS TRUE"))
    for role_code in (
        "ORGANIZATION_ADMIN",
        "SCHOOL_ADMIN",
        "ACCOUNTS",
        "TEACHER",
        "RECEPTIONIST",
        "PARENT_STUDENT",
    ):
        bind.execute(
            sa.text(
                "UPDATE users u SET account_type=:code WHERE u.is_superuser IS FALSE AND EXISTS ("
                "SELECT 1 FROM user_roles ur JOIN roles r ON r.id=ur.role_id WHERE ur.user_id=u.id AND r.code=:code)"
            ),
            {"code": role_code},
        )


def downgrade() -> None:
    # This release intentionally contains a non-trivial RBAC normalization.
    # Structural downgrade is provided; role naming should be restored from a DB backup if required.
    op.drop_constraint("uq_student_charge_source_year", "student_charges", type_="unique")
    op.drop_column("student_charges", "source_ref")
    op.drop_column("student_charges", "source_type")
    op.drop_table("student_erp_access")
    op.drop_table("erp_access_policies")
    op.drop_table("parent_student_links")
    op.drop_table("annual_correction_usage")
    op.drop_index("ix_parent_student_org_phone_unique", table_name="users")
    op.drop_index("ix_users_account_type", table_name="users")
    op.drop_column("users", "must_change_password")
    op.drop_column("users", "account_type")
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.drop_index("ix_school_udise_active_unique", table_name="school_udise_codes")
    op.drop_index("ix_school_udise_codes_school_id", table_name="school_udise_codes")
    op.drop_table("school_udise_codes")
    op.drop_index("ix_school_code_registry_organization_id", table_name="school_code_registry")
    op.drop_table("school_code_registry")
    op.drop_index("ix_schools_org_code", table_name="schools")
    op.create_index(
        "ix_schools_code",
        "schools",
        ["code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_schools_udise_code",
        "schools",
        ["udise_code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    for name in (
        "principal_head_phone",
        "principal_head_email",
        "principal_head_name",
        "tagline",
        "area_code",
        "area",
    ):
        op.drop_column("school_configurations", name)
    for name in ("head_phone", "head_email", "head_full_name", "allowed_schools"):
        op.drop_column("organizations", name)
