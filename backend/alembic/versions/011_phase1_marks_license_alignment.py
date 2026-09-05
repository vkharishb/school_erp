"""phase1 marks and 31-May license alignment

Revision ID: 011
Revises: 010
"""

from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "student_marks",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "school_id", sa.Uuid(), sa.ForeignKey("schools.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "campus_id",
            sa.Uuid(),
            sa.ForeignKey("campuses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "academic_year_id",
            sa.Uuid(),
            sa.ForeignKey("academic_years.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("students.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "subject_id",
            sa.Uuid(),
            sa.ForeignKey("subjects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("assessment_name", sa.String(120), nullable=False),
        sa.Column("max_marks", sa.Numeric(8, 2), nullable=False),
        sa.Column("marks_obtained", sa.Numeric(8, 2), nullable=False),
        sa.Column("remarks", sa.String(500)),
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("entered_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("locked_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "school_id",
            "academic_year_id",
            "student_id",
            "subject_id",
            "assessment_name",
            name="uq_student_mark_assessment",
        ),
    )
    for col in [
        "school_id",
        "campus_id",
        "academic_year_id",
        "student_id",
        "subject_id",
        "entered_by",
        "locked_by",
    ]:
        op.create_index(f"ix_student_marks_{col}", "student_marks", [col])

    # Existing installations are normalized to the agreed annual 31-May policy.
    bind = op.get_bind()
    now = datetime.now(UTC)
    target_year = now.year if (now.month, now.day) <= (5, 31) else now.year + 1
    expiry = datetime(target_year, 5, 31, 18, 29, 59, tzinfo=UTC)  # 23:59:59 IST
    bind.execute(
        sa.text(
            "UPDATE organizations SET license_expires_at=:expiry WHERE license_expires_at IS NULL OR license_expires_at <> :expiry"
        ),
        {"expiry": expiry},
    )
    bind.execute(
        sa.text("UPDATE school_licenses SET expires_at=:expiry WHERE expires_at <> :expiry"),
        {"expiry": expiry},
    )
    bind.execute(
        sa.text(
            "UPDATE organizations SET enabled_modules = (enabled_modules::jsonb || '[\"marks\"]'::jsonb)::json WHERE NOT (enabled_modules::jsonb ? 'marks')"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE school_licenses SET enabled_modules = (enabled_modules::jsonb || '[\"marks\"]'::jsonb)::json WHERE NOT (enabled_modules::jsonb ? 'marks')"
        )
    )


def downgrade():
    op.drop_table("student_marks")
