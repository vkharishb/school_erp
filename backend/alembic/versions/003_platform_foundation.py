"""Platform foundation: organizations, campuses, academic years, sessions, audit, approvals.

Revision ID: 003
Revises: 002
"""

import uuid
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "campuses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address_line1", sa.String(255)),
        sa.Column("address_line2", sa.String(255)),
        sa.Column("city", sa.String(100)),
        sa.Column("state", sa.String(100)),
        sa.Column("country", sa.String(100)),
        sa.Column("pincode", sa.String(20)),
        sa.Column("phone", sa.String(30)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("school_id", "code", name="uq_campus_school_code"),
    )
    op.create_index("ix_campuses_school_id", "campuses", ["school_id"])

    op.create_table(
        "academic_years",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "campus_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campuses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("is_read_only", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column(
            "activated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("campus_id", "code", name="uq_academic_year_campus_code"),
    )
    op.create_index("ix_academic_years_campus_id", "academic_years", ["campus_id"])

    op.add_column(
        "schools", sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_schools_organization",
        "schools",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_schools_organization_id", "schools", ["organization_id"])

    op.add_column(
        "users", sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column("users", sa.Column("campus_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_users_organization",
        "users",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_users_campus", "users", "campuses", ["campus_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_index("ix_users_campus_id", "users", ["campus_id"])

    op.add_column(
        "roles", sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column("roles", sa.Column("campus_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_roles_organization",
        "roles",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_roles_campus", "roles", "campuses", ["campus_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_roles_organization_id", "roles", ["organization_id"])
    op.create_index("ix_roles_campus_id", "roles", ["campus_id"])

    op.add_column(
        "role_permissions",
        sa.Column("data_scope", postgresql.JSON(), nullable=False, server_default="{}"),
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("device_name", sa.String(255)),
        sa.Column("user_agent", sa.String(1000)),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "campus_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("module", sa.String(50)),
        sa.Column("entity_type", sa.String(100)),
        sa.Column("entity_id", sa.String(100)),
        sa.Column("before_data", postgresql.JSON()),
        sa.Column("after_data", postgresql.JSON()),
        sa.Column("metadata_json", postgresql.JSON()),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("user_agent", sa.String(1000)),
        sa.Column("correlation_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_school_created", "audit_events", ["school_id", "created_at"])
    op.create_index("ix_audit_entity", "audit_events", ["entity_type", "entity_id"])
    op.create_index("ix_audit_correlation_id", "audit_events", ["correlation_id"])

    op.create_table(
        "approval_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "campus_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "requested_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("request_type", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100)),
        sa.Column("entity_id", sa.String(100)),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reason", sa.Text()),
        sa.Column("payload", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "decided_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decision_comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_approval_scope_status", "approval_requests", ["school_id", "status", "created_at"]
    )

    # Backfill a one-to-one organization and campus for every existing school.
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, code FROM schools")).mappings().all()
    for row in rows:
        org_id = uuid.uuid4()
        campus_id = uuid.uuid4()
        bind.execute(
            sa.text(
                "INSERT INTO organizations (id, code, name, is_active, created_at, updated_at) VALUES (:id, :code, :name, true, now(), now())"
            ),
            {"id": org_id, "code": f"ORG-{row['code']}", "name": f"Organization for {row['code']}"},
        )
        bind.execute(
            sa.text("UPDATE schools SET organization_id = :org_id WHERE id = :school_id"),
            {"org_id": org_id, "school_id": row["id"]},
        )
        bind.execute(
            sa.text(
                "INSERT INTO campuses (id, school_id, code, name, is_active, created_at, updated_at) VALUES (:id, :school_id, 'MAIN', 'Main Campus', true, now(), now())"
            ),
            {"id": campus_id, "school_id": row["id"]},
        )
        bind.execute(
            sa.text(
                "UPDATE users SET organization_id = :org_id, campus_id = :campus_id WHERE school_id = :school_id"
            ),
            {"org_id": org_id, "campus_id": campus_id, "school_id": row["id"]},
        )
        bind.execute(
            sa.text("UPDATE roles SET organization_id = :org_id WHERE school_id = :school_id"),
            {"org_id": org_id, "school_id": row["id"]},
        )


def downgrade() -> None:
    op.drop_index("ix_approval_scope_status", table_name="approval_requests")
    op.drop_table("approval_requests")
    op.drop_index("ix_audit_correlation_id", table_name="audit_events")
    op.drop_index("ix_audit_entity", table_name="audit_events")
    op.drop_index("ix_audit_school_created", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_column("role_permissions", "data_scope")
    op.drop_index("ix_roles_campus_id", table_name="roles")
    op.drop_index("ix_roles_organization_id", table_name="roles")
    op.drop_constraint("fk_roles_campus", "roles", type_="foreignkey")
    op.drop_constraint("fk_roles_organization", "roles", type_="foreignkey")
    op.drop_column("roles", "campus_id")
    op.drop_column("roles", "organization_id")
    op.drop_index("ix_users_campus_id", table_name="users")
    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_constraint("fk_users_campus", "users", type_="foreignkey")
    op.drop_constraint("fk_users_organization", "users", type_="foreignkey")
    op.drop_column("users", "campus_id")
    op.drop_column("users", "organization_id")
    op.drop_index("ix_schools_organization_id", table_name="schools")
    op.drop_constraint("fk_schools_organization", "schools", type_="foreignkey")
    op.drop_column("schools", "organization_id")
    op.drop_index("ix_academic_years_campus_id", table_name="academic_years")
    op.drop_table("academic_years")
    op.drop_index("ix_campuses_school_id", table_name="campuses")
    op.drop_table("campuses")
    op.drop_table("organizations")
