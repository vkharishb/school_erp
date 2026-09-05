"""Phase 1 security, organization licensing and teacher assignment controls.

Revision ID: 010
Revises: 009
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PHASE1 = '["dashboard", "school_admin", "student", "teacher", "attendance", "fee"]'


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("enabled_modules", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "organizations", sa.Column("license_starts_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "organizations", sa.Column("license_expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute(
        f"UPDATE organizations SET enabled_modules = '{PHASE1}'::jsonb WHERE enabled_modules IS NULL"
    )
    op.execute(
        "UPDATE organizations SET license_starts_at = COALESCE(created_at, now()) WHERE license_starts_at IS NULL"
    )
    op.execute(
        "UPDATE organizations SET license_expires_at = make_timestamptz(CASE WHEN EXTRACT(MONTH FROM now() AT TIME ZONE 'Asia/Kolkata') > 5 OR (EXTRACT(MONTH FROM now() AT TIME ZONE 'Asia/Kolkata') = 5 AND EXTRACT(DAY FROM now() AT TIME ZONE 'Asia/Kolkata') > 31) THEN EXTRACT(YEAR FROM now() AT TIME ZONE 'Asia/Kolkata')::int + 1 ELSE EXTRACT(YEAR FROM now() AT TIME ZONE 'Asia/Kolkata')::int END, 5, 31, 23, 59, 59, 'Asia/Kolkata') WHERE license_expires_at IS NULL"
    )
    op.alter_column("organizations", "enabled_modules", nullable=False)


def downgrade() -> None:
    op.drop_column("organizations", "license_expires_at")
    op.drop_column("organizations", "license_starts_at")
    op.drop_column("organizations", "enabled_modules")
