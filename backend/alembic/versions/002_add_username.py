"""Add username to users; email optional

Revision ID: 002
Revises: 001
Create Date: 2026-08-07
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=100), nullable=True))
    # Backfill existing rows from email local-part or id
    op.execute(
        """
        UPDATE users
        SET username = COALESCE(
            NULLIF(split_part(email, '@', 1), ''),
            'user_' || substr(id::text, 1, 8)
        )
        WHERE username IS NULL
        """
    )
    op.alter_column("users", "username", nullable=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    # Allow email to be null for non-admin roles later
    op.alter_column("users", "email", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
    op.alter_column("users", "email", existing_type=sa.String(length=255), nullable=False)
