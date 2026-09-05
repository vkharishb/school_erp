"""phase1 admin access, academic permissions and teacher import fields

Revision ID: 013
Revises: 012
"""

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = [
    ("academic_class.manage", "Manage classes & sections", "school_config"),
    ("subject.manage", "Manage subjects", "school_config"),
    ("system.settings.manage", "Manage platform system settings", "school_admin"),
]


def _permission_id(bind, code: str):
    return bind.execute(
        sa.text("SELECT id FROM permissions WHERE code=:code"), {"code": code}
    ).scalar_one_or_none()


def _role_ids(bind, code: str):
    return list(
        bind.execute(sa.text("SELECT id FROM roles WHERE code=:code"), {"code": code})
        .scalars()
        .all()
    )


def _ensure_role_permission(bind, role_id, permission_id):
    exists = bind.execute(
        sa.text("SELECT 1 FROM role_permissions WHERE role_id=:rid AND permission_id=:pid"),
        {"rid": role_id, "pid": permission_id},
    ).scalar_one_or_none()
    if not exists:
        bind.execute(
            sa.text(
                "INSERT INTO role_permissions (id, role_id, permission_id, data_scope) VALUES (:id, :rid, :pid, CAST(:scope AS JSON))"
            ),
            {"id": uuid.uuid4(), "rid": role_id, "pid": permission_id, "scope": "{}"},
        )


def upgrade():
    op.add_column("teachers", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("teachers", sa.Column("government_id", sa.String(length=100), nullable=True))
    op.add_column("teachers", sa.Column("category", sa.String(length=100), nullable=True))
    op.add_column("teachers", sa.Column("sub_category", sa.String(length=100), nullable=True))
    op.add_column("teachers", sa.Column("custom_fields", postgresql.JSON(), nullable=True))
    op.execute("UPDATE teachers SET custom_fields = '{}'::json WHERE custom_fields IS NULL")
    op.alter_column("teachers", "custom_fields", nullable=False)

    bind = op.get_bind()
    for code, name, module in NEW_PERMISSIONS:
        if not _permission_id(bind, code):
            bind.execute(
                sa.text(
                    "INSERT INTO permissions (id, code, name, module) VALUES (:id, :code, :name, :module)"
                ),
                {"id": uuid.uuid4(), "code": code, "name": name, "module": module},
            )

    # Privileged platform controls must never be inherited by tenant roles.
    bind.execute(
        sa.text("""
        DELETE FROM role_permissions rp
        USING roles r, permissions p
        WHERE rp.role_id=r.id AND rp.permission_id=p.id
          AND r.code <> 'PLATFORM_SUPER_ADMIN'
          AND p.code IN ('role.manage','module.manage','system.settings.manage')
    """)
    )
    # School configuration editing and school-wide audit are restricted to School Admin / Super Admin.
    bind.execute(
        sa.text("""
        DELETE FROM role_permissions rp
        USING roles r, permissions p
        WHERE rp.role_id=r.id AND rp.permission_id=p.id
          AND r.code IN ('CAMPUS_ADMIN','PRINCIPAL')
          AND p.code IN ('school.config.edit','audit.view')
    """)
    )

    for role_code in ("SCHOOL_ADMIN", "CAMPUS_ADMIN", "PRINCIPAL"):
        for role_id in _role_ids(bind, role_code):
            for permission_code in ("academic_class.manage", "subject.manage"):
                permission_id = _permission_id(bind, permission_code)
                if permission_id:
                    _ensure_role_permission(bind, role_id, permission_id)

    for role_id in _role_ids(bind, "PLATFORM_SUPER_ADMIN"):
        for permission_code in (
            "academic_class.manage",
            "subject.manage",
            "system.settings.manage",
        ):
            permission_id = _permission_id(bind, permission_code)
            if permission_id:
                _ensure_role_permission(bind, role_id, permission_id)


def downgrade():
    op.drop_column("teachers", "custom_fields")
    op.drop_column("teachers", "sub_category")
    op.drop_column("teachers", "category")
    op.drop_column("teachers", "government_id")
    op.drop_column("teachers", "date_of_birth")
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code IN ('academic_class.manage','subject.manage','system.settings.manage'))"
    )
    op.execute(
        "DELETE FROM permissions WHERE code IN ('academic_class.manage','subject.manage','system.settings.manage')"
    )
