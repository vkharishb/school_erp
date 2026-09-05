"""Phase 1 teacher and attendance core.

Revision ID: 009
Revises: 008
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "teachers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "campus_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campuses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("employee_code", sa.String(50), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(30)),
        sa.Column("designation", sa.String(100)),
        sa.Column("qualification", sa.String(255)),
        sa.Column("joining_date", sa.Date()),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("school_id", "employee_code", name="uq_teacher_school_employee_code"),
        sa.UniqueConstraint("user_id", name="uq_teachers_user_id"),
    )
    op.create_index("ix_teachers_school_id", "teachers", ["school_id"])
    op.create_index("ix_teachers_campus_id", "teachers", ["campus_id"])
    op.create_index("ix_teachers_user_id", "teachers", ["user_id"])

    for table, entity, fk in (
        ("student_attendance", "students", "student_id"),
        ("teacher_attendance", "teachers", "teacher_id"),
    ):
        op.create_table(
            table,
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "school_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("schools.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "campus_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("campuses.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                fk,
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{entity}.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("attendance_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="present"),
            sa.Column("remarks", sa.Text()),
            sa.Column(
                "marked_by",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
            ),
            sa.Column("marked_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                fk, "attendance_date", name=f"uq_{table.replace('_attendance', '')}_attendance_day"
            ),
        )
        op.create_index(f"ix_{table}_school_id", table, ["school_id"])
        op.create_index(f"ix_{table}_campus_id", table, ["campus_id"])
        op.create_index(f"ix_{table}_{fk}", table, [fk])
        op.create_index(f"ix_{table}_attendance_date", table, ["attendance_date"])


def downgrade() -> None:
    op.drop_table("teacher_attendance")
    op.drop_table("student_attendance")
    op.drop_table("teachers")
