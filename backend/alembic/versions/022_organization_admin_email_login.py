"""Organization Admin case-insensitive email login uniqueness.

Revision ID: 022
Revises: 021
"""

import sqlalchemy as sa

from alembic import op

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    collision = bind.execute(
        sa.text(
            "SELECT lower(btrim(email)) AS normalized, count(*) AS n "
            "FROM users "
            "WHERE account_type='ORGANIZATION_ADMIN' AND email IS NOT NULL "
            "GROUP BY lower(btrim(email)) HAVING count(*) > 1 LIMIT 1"
        )
    ).first()
    if collision:
        raise RuntimeError(
            f"Cannot enable Organization Admin email login: duplicate email exists for "
            f"{collision.normalized!r}. Resolve the duplicate accounts before applying migration 022."
        )
    bind.execute(
        sa.text(
            "UPDATE users SET email=lower(btrim(email)) "
            "WHERE account_type='ORGANIZATION_ADMIN' AND email IS NOT NULL"
        )
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_org_admin_email_ci ON users (lower(email)) "
        "WHERE account_type='ORGANIZATION_ADMIN' AND email IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("uq_org_admin_email_ci", table_name="users")
