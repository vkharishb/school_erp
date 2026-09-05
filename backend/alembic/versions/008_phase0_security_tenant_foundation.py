"""Phase 0 security and tenant foundation.

Revision ID: 008
Revises: 007
"""

import uuid
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("schools", sa.Column("udise_code", sa.String(50), nullable=True))
    op.create_index("ix_schools_udise_code", "schools", ["udise_code"], unique=True)

    op.create_table(
        "organization_academic_years",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
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
        sa.UniqueConstraint("organization_id", "code", name="uq_org_academic_year_code"),
    )
    op.create_index(
        "ix_organization_academic_years_organization_id",
        "organization_academic_years",
        ["organization_id"],
    )
    op.add_column(
        "academic_years",
        sa.Column("organization_academic_year_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_academic_years_organization_academic_year",
        "academic_years",
        "organization_academic_years",
        ["organization_academic_year_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_academic_years_organization_academic_year_id",
        "academic_years",
        ["organization_academic_year_id"],
    )

    op.add_column(
        "user_sessions",
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "user_sessions",
        sa.Column("parent_session_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "user_sessions",
        sa.Column("replaced_by_session_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("user_sessions", sa.Column("revocation_reason", sa.String(50)))
    op.add_column("user_sessions", sa.Column("reuse_detected_at", sa.DateTime(timezone=True)))

    bind = op.get_bind()
    session_ids = bind.execute(sa.text("SELECT id FROM user_sessions")).scalars().all()
    for session_id in session_ids:
        bind.execute(
            sa.text("UPDATE user_sessions SET family_id = :family_id WHERE id = :session_id"),
            {"family_id": uuid.uuid4(), "session_id": session_id},
        )
    op.alter_column("user_sessions", "family_id", nullable=False)
    op.create_foreign_key(
        "fk_user_sessions_parent",
        "user_sessions",
        "user_sessions",
        ["parent_session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_user_sessions_replacement",
        "user_sessions",
        "user_sessions",
        ["replaced_by_session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_user_sessions_family_id", "user_sessions", ["family_id"])
    op.create_index("ix_user_sessions_parent_session_id", "user_sessions", ["parent_session_id"])
    op.create_index(
        "ix_user_sessions_replaced_by_session_id",
        "user_sessions",
        ["replaced_by_session_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_sessions_replaced_by_session_id", table_name="user_sessions")
    op.drop_index("ix_user_sessions_parent_session_id", table_name="user_sessions")
    op.drop_index("ix_user_sessions_family_id", table_name="user_sessions")
    op.drop_constraint("fk_user_sessions_replacement", "user_sessions", type_="foreignkey")
    op.drop_constraint("fk_user_sessions_parent", "user_sessions", type_="foreignkey")
    op.drop_column("user_sessions", "reuse_detected_at")
    op.drop_column("user_sessions", "revocation_reason")
    op.drop_column("user_sessions", "replaced_by_session_id")
    op.drop_column("user_sessions", "parent_session_id")
    op.drop_column("user_sessions", "family_id")

    op.drop_index("ix_academic_years_organization_academic_year_id", table_name="academic_years")
    op.drop_constraint(
        "fk_academic_years_organization_academic_year", "academic_years", type_="foreignkey"
    )
    op.drop_column("academic_years", "organization_academic_year_id")
    op.drop_index(
        "ix_organization_academic_years_organization_id",
        table_name="organization_academic_years",
    )
    op.drop_table("organization_academic_years")
    op.drop_index("ix_schools_udise_code", table_name="schools")
    op.drop_column("schools", "udise_code")
