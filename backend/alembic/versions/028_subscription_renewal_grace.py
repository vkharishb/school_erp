"""subscription renewal grace

Revision ID: 028
Revises: 027
"""
from alembic import op
import sqlalchemy as sa

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("organization_subscriptions", sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_organization_subscriptions_grace_until", "organization_subscriptions", ["grace_until"])
    op.execute("UPDATE organization_subscriptions SET grace_until = expires_at + INTERVAL '30 days' WHERE billing_cycle <> 'trial'")
    op.execute("UPDATE school_subscriptions ss SET expires_at = os.expires_at + INTERVAL '30 days' FROM organization_subscriptions os WHERE ss.organization_subscription_id = os.id AND os.billing_cycle <> 'trial'")
    op.execute("UPDATE school_licenses sl SET expires_at = os.expires_at + INTERVAL '30 days' FROM school_subscriptions ss JOIN organization_subscriptions os ON os.id = ss.organization_subscription_id WHERE sl.school_id = ss.school_id AND os.billing_cycle <> 'trial'")

def downgrade():
    op.drop_index("ix_organization_subscriptions_grace_until", table_name="organization_subscriptions")
    op.drop_column("organization_subscriptions", "grace_until")
