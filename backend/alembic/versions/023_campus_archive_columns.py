"""Synchronize Campus archive columns with the ORM model.

Revision ID: 023
Revises: 022
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "campuses",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "campuses",
        sa.Column("archived_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_campuses_archived_at",
        "campuses",
        ["archived_at"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_campuses_archived_by_users",
        "campuses",
        "users",
        ["archived_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_campuses_archived_by_users",
        "campuses",
        type_="foreignkey",
    )
    op.drop_index("ix_campuses_archived_at", table_name="campuses")
    op.drop_column("campuses", "archived_by")
    op.drop_column("campuses", "archived_at")
