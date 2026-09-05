"""add missing campus module and license columns

Revision ID: 012
Revises: 011

The Campus ORM model has carried enabled_modules, license_starts_at and
license_expires_at, but the database migration chain through 011 never added
those columns to the campuses table.  Creating a school therefore failed when
SQLAlchemy attempted to INSERT the ORM columns.

This migration brings PostgreSQL into sync with the ORM model and safely
backfills existing campuses from their school's license.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "campuses",
        sa.Column(
            "enabled_modules",
            postgresql.JSON(),
            nullable=True,
        ),
    )
    op.add_column(
        "campuses",
        sa.Column("license_starts_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "campuses",
        sa.Column("license_expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Existing MAIN campuses inherit the effective per-school license.
    op.execute(
        """
        UPDATE campuses AS c
        SET
            enabled_modules = COALESCE(sl.enabled_modules, '[]'::json),
            license_starts_at = sl.starts_at,
            license_expires_at = sl.expires_at
        FROM school_licenses AS sl
        WHERE sl.school_id = c.school_id
        """
    )

    # Defensive backfill for any campus that has no school-license row.
    op.execute(
        """
        UPDATE campuses
        SET enabled_modules = '[]'::json
        WHERE enabled_modules IS NULL
        """
    )

    op.alter_column("campuses", "enabled_modules", nullable=False)


def downgrade():
    op.drop_column("campuses", "license_expires_at")
    op.drop_column("campuses", "license_starts_at")
    op.drop_column("campuses", "enabled_modules")
