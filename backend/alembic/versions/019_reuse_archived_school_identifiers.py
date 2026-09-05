"""Allow archived school code and UDISE identifiers to be reused.

Revision ID: 019
Revises: 018
"""

import sqlalchemy as sa

from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rev3 soft-deletes schools but the pre-existing global unique indexes still
    # reserve code/UDISE forever. Replace them with active-row-only uniqueness.
    op.drop_index("ix_schools_code", table_name="schools")
    op.drop_index("ix_schools_udise_code", table_name="schools")

    op.create_index(
        "ix_schools_code",
        "schools",
        ["code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_schools_udise_code",
        "schools",
        ["udise_code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_schools_udise_code", table_name="schools")
    op.drop_index("ix_schools_code", table_name="schools")

    # Downgrade can only succeed if archived rows do not duplicate identifiers.
    op.create_index("ix_schools_code", "schools", ["code"], unique=True)
    op.create_index("ix_schools_udise_code", "schools", ["udise_code"], unique=True)
