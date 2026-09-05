"""admin edit controls and granular fee setup/import permissions

Revision ID: 014
Revises: 013
"""

import uuid

import sqlalchemy as sa

from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None

NEW_PERMISSIONS = [
    ("fee.head.manage", "Manage fee heads", "fee"),
    ("fee.structure.manage", "Manage fee structures", "fee"),
    ("fee.structure.bulk_upload", "Bulk upload fee structures", "fee"),
    ("fee.dues.bulk_upload", "Bulk upload prior-year dues", "fee"),
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
    bind = op.get_bind()
    for code, name, module in NEW_PERMISSIONS:
        if not _permission_id(bind, code):
            bind.execute(
                sa.text(
                    "INSERT INTO permissions (id, code, name, module) VALUES (:id, :code, :name, :module)"
                ),
                {"id": uuid.uuid4(), "code": code, "name": name, "module": module},
            )

    # Platform and School Admin manage all setup/import operations.
    for role_code in ("PLATFORM_SUPER_ADMIN", "SCHOOL_ADMIN"):
        for role_id in _role_ids(bind, role_code):
            for permission_code, _name, _module in NEW_PERMISSIONS:
                permission_id = _permission_id(bind, permission_code)
                if permission_id:
                    _ensure_role_permission(bind, role_id, permission_id)

    # Accountant may configure fee heads/structures but financial bulk import remains admin-only.
    for role_id in _role_ids(bind, "ACCOUNTANT"):
        for permission_code in ("fee.head.manage", "fee.structure.manage"):
            permission_id = _permission_id(bind, permission_code)
            if permission_id:
                _ensure_role_permission(bind, role_id, permission_id)


def downgrade():
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code IN ('fee.head.manage','fee.structure.manage','fee.structure.bulk_upload','fee.dues.bulk_upload'))"
        )
    )
    bind.execute(
        sa.text(
            "DELETE FROM permissions WHERE code IN ('fee.head.manage','fee.structure.manage','fee.structure.bulk_upload','fee.dues.bulk_upload')"
        )
    )
