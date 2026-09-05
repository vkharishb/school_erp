"""Admin governance: organization archive and case-insensitive usernames.

Revision ID: 021
Revises: 020
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "organizations", sa.Column("archived_by", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_index("ix_organizations_archived_at", "organizations", ["archived_at"], unique=False)
    op.create_foreign_key(
        "fk_organizations_archived_by_users",
        "organizations",
        "users",
        ["archived_by"],
        ["id"],
        ondelete="SET NULL",
    )

    bind = op.get_bind()
    collision = bind.execute(
        sa.text(
            "SELECT lower(btrim(username)) AS normalized, count(*) AS n "
            "FROM users GROUP BY lower(btrim(username)) HAVING count(*) > 1 LIMIT 1"
        )
    ).first()
    if collision:
        raise RuntimeError(
            f"Cannot enable case-insensitive usernames: duplicate usernames exist for {collision.normalized!r}. "
            "Resolve the duplicate accounts before applying migration 021."
        )
    bind.execute(sa.text("UPDATE users SET username=lower(btrim(username))"))
    op.execute("CREATE UNIQUE INDEX uq_users_username_ci ON users (lower(username))")


def downgrade() -> None:
    op.drop_index("uq_users_username_ci", table_name="users")
    op.drop_constraint("fk_organizations_archived_by_users", "organizations", type_="foreignkey")
    op.drop_index("ix_organizations_archived_at", table_name="organizations")
    op.drop_column("organizations", "archived_by")
    op.drop_column("organizations", "archived_at")
