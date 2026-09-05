"""Add user designation for admin profile identity.

Revision ID: 025
Revises: 024
"""

import sqlalchemy as sa

from alembic import op

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("designation", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "designation")
