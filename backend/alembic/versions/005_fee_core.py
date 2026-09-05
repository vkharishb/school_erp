"""Fee configuration, charges, payments and allocation ledger.

Revision ID: 005
Revises: 004
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fee_heads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("is_misc", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("school_id", "code", name="uq_fee_head_school_code"),
    )
    op.create_index("ix_fee_heads_school_id", "fee_heads", ["school_id"])

    op.create_table(
        "fee_structure_items",
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
        sa.Column(
            "academic_year_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("academic_years.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "academic_class_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("academic_classes.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "section_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sections.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "fee_head_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fee_heads.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("frequency", sa.String(30), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_fee_structure_scope",
        "fee_structure_items",
        ["school_id", "campus_id", "academic_year_id", "academic_class_id"],
    )

    op.create_table(
        "student_charges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("students.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "academic_year_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("academic_years.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "fee_head_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fee_heads.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_student_charge_student_status", "student_charges", ["student_id", "status"])

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("students.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_mode", sa.String(50), nullable=False),
        sa.Column("upi_reference_last5", sa.String(5)),
        sa.Column("receipt_number", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="posted"),
        sa.Column(
            "collected_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancellation_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("school_id", "receipt_number", name="uq_payment_school_receipt"),
    )
    op.create_index("ix_payments_school_id", "payments", ["school_id"])
    op.create_index("ix_payments_student_id", "payments", ["student_id"])

    op.create_table(
        "payment_allocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "payment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "charge_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("student_charges.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.UniqueConstraint("payment_id", "charge_id", name="uq_payment_charge_allocation"),
    )


def downgrade() -> None:
    op.drop_table("payment_allocations")
    op.drop_index("ix_payments_student_id", table_name="payments")
    op.drop_index("ix_payments_school_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_student_charge_student_status", table_name="student_charges")
    op.drop_table("student_charges")
    op.drop_index("ix_fee_structure_scope", table_name="fee_structure_items")
    op.drop_table("fee_structure_items")
    op.drop_index("ix_fee_heads_school_id", table_name="fee_heads")
    op.drop_table("fee_heads")
