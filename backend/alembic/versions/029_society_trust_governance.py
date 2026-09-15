"""society trust governance

Revision ID: 029
Revises: 028
"""
from alembic import op
import sqlalchemy as sa

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("organizations", sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("organizations", sa.Column("disabled_by", sa.UUID(), nullable=True))
    op.add_column("organizations", sa.Column("disable_reason", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column("deletion_information_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("organizations", sa.Column("operational_data_deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_organizations_disabled_by_users", "organizations", "users", ["disabled_by"], ["id"], ondelete="SET NULL")
    op.add_column("organization_subscriptions", sa.Column("activation_minimum_original", sa.Numeric(14,2), nullable=False, server_default="0"))
    op.add_column("organization_subscriptions", sa.Column("activation_override_used", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("organization_subscriptions", sa.Column("activation_override_reason", sa.Text(), nullable=True))
    op.add_column("organization_subscriptions", sa.Column("activation_overridden_by", sa.UUID(), nullable=True))
    op.add_column("organization_subscriptions", sa.Column("activation_overridden_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_org_sub_activation_override_user", "organization_subscriptions", "users", ["activation_overridden_by"], ["id"], ondelete="SET NULL")
    op.execute("UPDATE organization_subscriptions SET activation_minimum_original = activation_minimum_amount")

def downgrade():
    op.drop_constraint("fk_org_sub_activation_override_user", "organization_subscriptions", type_="foreignkey")
    for col in ["activation_overridden_at","activation_overridden_by","activation_override_reason","activation_override_used","activation_minimum_original"]:
        op.drop_column("organization_subscriptions", col)
    op.drop_constraint("fk_organizations_disabled_by_users", "organizations", type_="foreignkey")
    for col in ["operational_data_deleted_at","deletion_information_sent_at","disable_reason","disabled_by","disabled_at"]:
        op.drop_column("organizations", col)
