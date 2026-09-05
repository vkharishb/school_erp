"""Configurable, auditable receipt numbering foundation.

Revision ID: 007
Revises: 006
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("campus_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_payments_campus", "payments", "campuses", ["campus_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_payments_campus_id", "payments", ["campus_id"])
    op.execute(
        "UPDATE payments p SET campus_id = s.campus_id FROM students s WHERE s.id = p.student_id"
    )
    op.alter_column("payments", "campus_id", nullable=False)

    op.create_table(
        "receipt_sequences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campus_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campuses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_key", sa.String(20), nullable=False),
        sa.Column("next_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "school_id", "campus_id", "period_key", name="uq_receipt_sequence_scope"
        ),
    )


def downgrade() -> None:
    op.drop_table("receipt_sequences")
    op.drop_index("ix_payments_campus_id", table_name="payments")
    op.drop_constraint("fk_payments_campus", "payments", type_="foreignkey")
    op.drop_column("payments", "campus_id")
