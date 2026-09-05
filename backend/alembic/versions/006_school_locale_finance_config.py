"""School locale and financial configuration fields.

Revision ID: 006
Revises: 005
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "school_configurations",
        sa.Column("timezone", sa.String(100), nullable=False, server_default="Asia/Kolkata"),
    )
    op.add_column(
        "school_configurations",
        sa.Column("currency", sa.String(10), nullable=False, server_default="INR"),
    )
    op.add_column(
        "school_configurations",
        sa.Column("date_format", sa.String(30), nullable=False, server_default="DD-MM-YYYY"),
    )
    op.add_column(
        "school_configurations",
        sa.Column("time_format", sa.String(20), nullable=False, server_default="12h"),
    )
    op.add_column(
        "school_configurations",
        sa.Column("fiscal_year_start_month", sa.Integer(), nullable=False, server_default="4"),
    )


def downgrade() -> None:
    op.drop_column("school_configurations", "fiscal_year_start_month")
    op.drop_column("school_configurations", "time_format")
    op.drop_column("school_configurations", "date_format")
    op.drop_column("school_configurations", "currency")
    op.drop_column("school_configurations", "timezone")
