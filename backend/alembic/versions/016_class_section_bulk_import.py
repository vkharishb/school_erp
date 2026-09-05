"""add class and section bulk import permissions

Revision ID: 016
Revises: 015
"""

import uuid

import sqlalchemy as sa

from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


NEW_PERMISSIONS = (
    ("academic_class.bulk_upload", "Bulk upload classes", "school_config"),
    ("section.bulk_upload", "Bulk upload sections", "school_config"),
)


def _permission_id(bind, code: str):
    return bind.execute(
        sa.text("SELECT id FROM permissions WHERE code=:code"),
        {"code": code},
    ).scalar_one_or_none()


def _role_ids(bind, code: str):
    return list(
        bind.execute(
            sa.text("SELECT id FROM roles WHERE code=:code"),
            {"code": code},
        )
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
                "INSERT INTO role_permissions "
                "(id, role_id, permission_id, data_scope) "
                "VALUES (:id, :rid, :pid, CAST(:scope AS JSON))"
            ),
            {
                "id": uuid.uuid4(),
                "rid": role_id,
                "pid": permission_id,
                "scope": "{}",
            },
        )


def upgrade():
    bind = op.get_bind()

    for code, name, module in NEW_PERMISSIONS:
        if not _permission_id(bind, code):
            bind.execute(
                sa.text(
                    "INSERT INTO permissions (id, code, name, module) "
                    "VALUES (:id, :code, :name, :module)"
                ),
                {
                    "id": uuid.uuid4(),
                    "code": code,
                    "name": name,
                    "module": module,
                },
            )

    # Academic structure bulk setup is available to administrative academic roles.
    for role_code in (
        "PLATFORM_SUPER_ADMIN",
        "SCHOOL_ADMIN",
        "CAMPUS_ADMIN",
        "PRINCIPAL",
    ):
        for role_id in _role_ids(bind, role_code):
            for permission_code, _name, _module in NEW_PERMISSIONS:
                permission_id = _permission_id(bind, permission_code)
                if permission_id:
                    _ensure_role_permission(bind, role_id, permission_id)


def downgrade():
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM role_permissions "
            "WHERE permission_id IN "
            "(SELECT id FROM permissions "
            " WHERE code IN ('academic_class.bulk_upload','section.bulk_upload'))"
        )
    )
    bind.execute(
        sa.text(
            "DELETE FROM permissions "
            "WHERE code IN ('academic_class.bulk_upload','section.bulk_upload')"
        )
    )
