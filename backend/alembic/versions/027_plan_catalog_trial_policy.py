"""plan catalog and trial policy

Revision ID: 027
Revises: 026
"""
from alembic import op
import sqlalchemy as sa

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("subscription_plans", sa.Column("student_limit", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("subscription_plans", sa.Column("teacher_limit", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("subscription_plans", sa.Column("minimum_students", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("subscription_plans", sa.Column("excess_student_yearly_rate", sa.Numeric(14,2), nullable=False, server_default="0"))
    op.add_column("subscription_plans", sa.Column("pricing_tiers", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))

def downgrade():
    for c in ["pricing_tiers","excess_student_yearly_rate","minimum_students","teacher_limit","student_limit"]:
        op.drop_column("subscription_plans", c)
