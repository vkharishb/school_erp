"""Academic structure and student core.

Revision ID: 004
Revises: 003
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "academic_classes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "campus_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campuses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("campus_id", "code", name="uq_academic_class_campus_code"),
    )
    op.create_index("ix_academic_classes_campus_id", "academic_classes", ["campus_id"])

    op.create_table(
        "sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "academic_class_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("academic_classes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("academic_class_id", "code", name="uq_section_class_code"),
    )
    op.create_index("ix_sections_academic_class_id", "sections", ["academic_class_id"])

    op.create_table(
        "subjects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "campus_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campuses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("campus_id", "code", name="uq_subject_campus_code"),
    )
    op.create_index("ix_subjects_campus_id", "subjects", ["campus_id"])

    op.create_table(
        "guardians",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "school_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schools.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("relationship_type", sa.String(50), nullable=False),
        sa.Column("mobile", sa.String(30)),
        sa.Column("email", sa.String(255)),
        sa.Column("occupation", sa.String(150)),
        sa.Column("address", sa.Text()),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("pickup_authorized", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_guardians_school_id", "guardians", ["school_id"])

    op.create_table(
        "students",
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
        sa.Column("student_code", sa.String(100), nullable=False, unique=True),
        sa.Column("admission_number", sa.String(100), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("middle_name", sa.String(100)),
        sa.Column("last_name", sa.String(100)),
        sa.Column("date_of_birth", sa.Date()),
        sa.Column("gender", sa.String(30)),
        sa.Column("government_id", sa.String(100)),
        sa.Column("photo_url", sa.String(500)),
        sa.Column("admission_date", sa.Date()),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("category", sa.String(100)),
        sa.Column("address_line1", sa.String(255)),
        sa.Column("address_line2", sa.String(255)),
        sa.Column("city", sa.String(100)),
        sa.Column("state", sa.String(100)),
        sa.Column("pincode", sa.String(20)),
        sa.Column("emergency_contact_name", sa.String(255)),
        sa.Column("emergency_contact_phone", sa.String(30)),
        sa.Column("custom_fields", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("school_id", "admission_number", name="uq_student_school_admission"),
    )
    op.create_index("ix_students_school_id", "students", ["school_id"])
    op.create_index("ix_students_campus_id", "students", ["campus_id"])

    op.create_table(
        "student_guardians",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("students.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "guardian_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("guardians.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "guardian_id", name="uq_student_guardian"),
    )
    op.create_index("ix_student_guardians_student_id", "student_guardians", ["student_id"])
    op.create_index("ix_student_guardians_guardian_id", "student_guardians", ["guardian_id"])

    op.create_table(
        "student_enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
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
            "academic_class_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("academic_classes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "section_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sections.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("roll_number", sa.String(30)),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("enrolled_on", sa.Date(), nullable=False),
        sa.Column("withdrawn_on", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "student_id", "academic_year_id", name="uq_student_academic_year_enrollment"
        ),
    )
    op.create_index("ix_student_enrollments_student_id", "student_enrollments", ["student_id"])
    op.create_index(
        "ix_student_enrollments_academic_year_id", "student_enrollments", ["academic_year_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_student_enrollments_academic_year_id", table_name="student_enrollments")
    op.drop_index("ix_student_enrollments_student_id", table_name="student_enrollments")
    op.drop_table("student_enrollments")
    op.drop_index("ix_student_guardians_guardian_id", table_name="student_guardians")
    op.drop_index("ix_student_guardians_student_id", table_name="student_guardians")
    op.drop_table("student_guardians")
    op.drop_index("ix_students_campus_id", table_name="students")
    op.drop_index("ix_students_school_id", table_name="students")
    op.drop_table("students")
    op.drop_index("ix_guardians_school_id", table_name="guardians")
    op.drop_table("guardians")
    op.drop_index("ix_subjects_campus_id", table_name="subjects")
    op.drop_table("subjects")
    op.drop_index("ix_sections_academic_class_id", table_name="sections")
    op.drop_table("sections")
    op.drop_index("ix_academic_classes_campus_id", table_name="academic_classes")
    op.drop_table("academic_classes")
