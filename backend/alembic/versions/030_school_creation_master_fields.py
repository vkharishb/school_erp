"""school creation master fields and globally unique school codes

Revision ID: 030
Revises: 029
"""
from alembic import op
import sqlalchemy as sa

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("school_configurations", sa.Column("district", sa.String(length=100), nullable=True))
    op.drop_constraint("uq_school_code_registry_org_code", "school_code_registry", type_="unique")
    op.create_unique_constraint("uq_school_code_registry_code", "school_code_registry", ["code"])

def downgrade():
    op.drop_constraint("uq_school_code_registry_code", "school_code_registry", type_="unique")
    op.create_unique_constraint("uq_school_code_registry_org_code", "school_code_registry", ["organization_id", "code"])
    op.drop_column("school_configurations", "district")
