"""QA/security hardening: dashboard permission

Revision ID: 017
Revises: 016
"""

import uuid

import sqlalchemy as sa

from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    permission_id = bind.execute(
        sa.text("SELECT id FROM permissions WHERE code='dashboard.view'")
    ).scalar_one_or_none()
    if not permission_id:
        permission_id = uuid.uuid4()
        bind.execute(
            sa.text(
                "INSERT INTO permissions (id, code, name, module) VALUES (:id, 'dashboard.view', 'View dashboard', 'dashboard')"
            ),
            {"id": permission_id},
        )
    role_ids = (
        bind.execute(
            sa.text(
                "SELECT id FROM roles WHERE code IN ('PLATFORM_SUPER_ADMIN','SCHOOL_ADMIN','CAMPUS_ADMIN','PRINCIPAL','ACCOUNTANT','RECEPTIONIST','TEACHER')"
            )
        )
        .scalars()
        .all()
    )
    for role_id in role_ids:
        exists = bind.execute(
            sa.text("SELECT 1 FROM role_permissions WHERE role_id=:rid AND permission_id=:pid"),
            {"rid": role_id, "pid": permission_id},
        ).scalar_one_or_none()
        if not exists:
            bind.execute(
                sa.text(
                    "INSERT INTO role_permissions (id, role_id, permission_id, data_scope) VALUES (:id,:rid,:pid,CAST(:scope AS JSON))"
                ),
                {"id": uuid.uuid4(), "rid": role_id, "pid": permission_id, "scope": "{}"},
            )


def downgrade():
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code='dashboard.view')"
        )
    )
    bind.execute(sa.text("DELETE FROM permissions WHERE code='dashboard.view'"))
