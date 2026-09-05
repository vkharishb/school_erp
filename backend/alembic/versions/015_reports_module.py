"""implement phase1 reports module and report export permission

Revision ID: 015
Revises: 014
"""

import uuid

import sqlalchemy as sa

from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


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
    exists = bind.execute(
        sa.text("SELECT id FROM module_definitions WHERE code='reports'")
    ).scalar_one_or_none()
    if not exists:
        bind.execute(
            sa.text(
                "INSERT INTO module_definitions (id, code, name, description, is_core, sort_order) VALUES (:id, 'reports', 'Reports', 'School operational and financial reports', true, 80)"
            ),
            {"id": uuid.uuid4()},
        )

    for code, name in (("reports.view", "View reports"), ("reports.export", "Export reports")):
        if not _permission_id(bind, code):
            bind.execute(
                sa.text(
                    "INSERT INTO permissions (id, code, name, module) VALUES (:id, :code, :name, 'reports')"
                ),
                {"id": uuid.uuid4(), "code": code, "name": name},
            )

    for role_code in (
        "PLATFORM_SUPER_ADMIN",
        "SCHOOL_ADMIN",
        "CAMPUS_ADMIN",
        "PRINCIPAL",
        "ACCOUNTANT",
    ):
        for role_id in _role_ids(bind, role_code):
            for permission_code in ("reports.view", "reports.export"):
                permission_id = _permission_id(bind, permission_code)
                if permission_id:
                    _ensure_role_permission(bind, role_id, permission_id)

    # Accountant needs fee.export to export the financial reports it is allowed to view.
    fee_export_id = _permission_id(bind, "fee.export")
    if fee_export_id:
        for role_id in _role_ids(bind, "ACCOUNTANT"):
            _ensure_role_permission(bind, role_id, fee_export_id)

    # Existing licensed organizations/schools/campuses receive the newly implemented
    # Phase 1 reports module. This is idempotent and preserves every existing module.
    bind.execute(
        sa.text("""
        UPDATE organizations
        SET enabled_modules = (enabled_modules::jsonb || '[\"reports\"]'::jsonb)::json
        WHERE NOT (enabled_modules::jsonb @> '[\"reports\"]'::jsonb)
    """)
    )
    bind.execute(
        sa.text("""
        UPDATE school_licenses
        SET enabled_modules = (enabled_modules::jsonb || '[\"reports\"]'::jsonb)::json
        WHERE NOT (enabled_modules::jsonb @> '[\"reports\"]'::jsonb)
    """)
    )
    bind.execute(
        sa.text("""
        UPDATE campuses
        SET enabled_modules = (enabled_modules::jsonb || '[\"reports\"]'::jsonb)::json
        WHERE NOT (enabled_modules::jsonb @> '[\"reports\"]'::jsonb)
    """)
    )


def downgrade():
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code='reports.export')"
        )
    )
    bind.execute(sa.text("DELETE FROM permissions WHERE code='reports.export'"))
    # Keep reports.view because it existed before this migration in older bootstrap data.
    bind.execute(
        sa.text(
            "UPDATE organizations SET enabled_modules = (SELECT COALESCE(json_agg(value), '[]'::json) FROM json_array_elements_text(enabled_modules) value WHERE value <> 'reports')"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE school_licenses SET enabled_modules = (SELECT COALESCE(json_agg(value), '[]'::json) FROM json_array_elements_text(enabled_modules) value WHERE value <> 'reports')"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE campuses SET enabled_modules = (SELECT COALESCE(json_agg(value), '[]'::json) FROM json_array_elements_text(enabled_modules) value WHERE value <> 'reports')"
        )
    )
    bind.execute(sa.text("DELETE FROM module_definitions WHERE code='reports'"))
