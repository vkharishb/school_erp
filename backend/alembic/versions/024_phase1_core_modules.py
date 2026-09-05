"""Normalize all Phase 1 modules as the mandatory School ERP core.

Revision ID: 024
Revises: 023
"""

import json

from alembic import op

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


PHASE1_MODULES = [
    "dashboard",
    "school_admin",
    "school_config",
    "student",
    "teacher",
    "fee",
    "marks",
    "attendance",
    "reports",
]


def upgrade() -> None:
    # Values are a fixed source-controlled catalogue, not runtime input. Using
    # explicit SQL literals keeps both online and `alembic --sql` migrations
    # deterministic; execution-time parameter dictionaries render as NULL in
    # Alembic offline mode.
    modules = json.dumps(PHASE1_MODULES).replace("'", "''")
    codes = ", ".join(f"'{code}'" for code in PHASE1_MODULES)
    op.execute(f"UPDATE organizations SET enabled_modules = '{modules}'::json")
    op.execute(f"UPDATE school_licenses SET enabled_modules = '{modules}'::json")
    op.execute(f"UPDATE campuses SET enabled_modules = '{modules}'::json")
    op.execute(f"UPDATE module_definitions SET is_core = true WHERE code IN ({codes})")


def downgrade() -> None:
    # License normalization is intentionally retained: a downgrade must not
    # silently remove access to mandatory modules from an existing School.
    pass
