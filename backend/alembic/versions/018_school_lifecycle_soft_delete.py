"""School lifecycle: soft delete support

Revision ID: 018
Revises: 017
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("schools", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "schools",
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_schools_deleted_at", "schools", ["deleted_at"], unique=False)
    op.create_foreign_key(
        "fk_schools_deleted_by_users",
        "schools",
        "users",
        ["deleted_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint("fk_schools_deleted_by_users", "schools", type_="foreignkey")
    op.drop_index("ix_schools_deleted_at", table_name="schools")
    op.drop_column("schools", "deleted_by")
    op.drop_column("schools", "deleted_at")
