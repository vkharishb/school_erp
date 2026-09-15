"""Remove Campus as an operational scope while preserving legacy data.

Revision ID: 033
Revises: 032

This is deliberately non-destructive. Existing campus rows and all foreign-keyed
operational records remain untouched. The migration only guarantees that every
School has one active MAIN compatibility row so new School-scoped APIs can keep
legacy non-null campus foreign keys populated until those columns are physically
retired in a later schema cleanup.
"""
from alembic import op

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO campuses (
            id, school_id, code, name, is_active, enabled_modules, created_at, updated_at
        )
        SELECT
            (md5(s.id::text || '-MAIN'))::uuid, s.id, 'MAIN', 'Main', TRUE, '[]'::json, now(), now()
        FROM schools s
        WHERE s.deleted_at IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM campuses c
              WHERE c.school_id = s.id AND c.is_active IS TRUE
          )
        """
    )
    op.execute(
        """
        UPDATE campuses c
        SET code = 'MAIN', updated_at = now()
        WHERE c.id = (
            SELECT c2.id FROM campuses c2
            WHERE c2.school_id = c.school_id AND c2.is_active IS TRUE
            ORDER BY (c2.code = 'MAIN') DESC, c2.created_at ASC
            LIMIT 1
        )
        AND NOT EXISTS (
            SELECT 1 FROM campuses x
            WHERE x.school_id = c.school_id AND x.code = 'MAIN'
        )
        """
    )


def downgrade() -> None:
    # Non-destructive migration: compatibility rows may now own legitimate FKs.
    # Never delete or rewrite them on downgrade.
    pass
