"""Subscription V2 foundation: school plan authority and immutable agreement/ledger scaffolding.

Revision ID: 034
Revises: 033
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organization_subscriptions", sa.Column("billing_mode", sa.String(20), nullable=False, server_default="organization"))
    op.add_column("organization_subscriptions", sa.Column("agreement_number", sa.String(80), nullable=True))
    op.add_column("organization_subscriptions", sa.Column("agreement_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_organization_subscriptions_agreement_number", "organization_subscriptions", ["agreement_number"], unique=True)

    op.add_column("school_subscriptions", sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("school_subscriptions", sa.Column("plan_snapshot", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::json")))
    op.add_column("school_subscriptions", sa.Column("billing_cycle", sa.String(20), nullable=True))
    op.add_column("school_subscriptions", sa.Column("base_student_capacity", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("school_subscriptions", sa.Column("approved_extra_capacity", sa.Integer(), nullable=False, server_default="0"))
    op.create_foreign_key("fk_school_subscriptions_plan_id", "school_subscriptions", "subscription_plans", ["plan_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_school_subscriptions_plan_id", "school_subscriptions", ["plan_id"])
    op.execute("""
        UPDATE school_subscriptions ss
        SET plan_id = os.plan_id,
            billing_cycle = os.billing_cycle,
            base_student_capacity = COALESCE(sp.student_limit, 0),
            plan_snapshot = json_build_object(
                'plan_id', sp.id, 'code', sp.code, 'name', sp.name,
                'student_limit', sp.student_limit, 'teacher_limit', sp.teacher_limit,
                'enabled_modules', sp.enabled_modules,
                'monthly_price', sp.monthly_price, 'yearly_price', sp.yearly_price
            )
        FROM organization_subscriptions os
        JOIN subscription_plans sp ON sp.id = os.plan_id
        WHERE ss.organization_subscription_id = os.id
    """)
    op.alter_column("school_subscriptions", "plan_id", nullable=False)
    op.alter_column("school_subscriptions", "billing_cycle", nullable=False)

    op.create_table("subscription_agreement_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_subscription_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organization_subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("change_type", sa.String(40), nullable=False, server_default="initial"),
        sa.Column("snapshot", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_subscription_id", "version_no", name="uq_subscription_agreement_version"),
    )
    op.create_index("ix_subscription_agreement_versions_org", "subscription_agreement_versions", ["organization_subscription_id"])
    op.create_table("subscription_commercial_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_subscription_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organization_subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_subscription_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("school_subscriptions.id", ondelete="SET NULL")),
        sa.Column("entry_type", sa.String(40), nullable=False),
        sa.Column("amount", sa.Numeric(14,2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("metadata_json", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_subscription_commercial_ledger_org", "subscription_commercial_ledger", ["organization_subscription_id"])
    op.create_index("ix_subscription_commercial_ledger_school", "subscription_commercial_ledger", ["school_subscription_id"])

    # Preserve the existing agreement as immutable version 1 and opening ledger entry.
    op.execute("""
        INSERT INTO subscription_agreement_versions
            (id, organization_subscription_id, version_no, change_type, snapshot, effective_at, accepted_at, created_by, created_at)
        SELECT gen_random_uuid(), os.id, 1, 'initial',
            json_build_object('legacy_plan_id', os.plan_id, 'billing_cycle', os.billing_cycle,
              'school_count', os.school_count, 'list_amount', os.list_amount,
              'discount_type', os.discount_type, 'discount_value', os.discount_value,
              'tax_mode', os.tax_mode, 'tax_rate', os.tax_rate, 'finalized_amount', os.finalized_amount,
              'activation_minimum_amount', os.activation_minimum_amount),
            os.starts_at, os.agreement_accepted_at, os.created_by, os.created_at
        FROM organization_subscriptions os
    """)
    op.execute("""
        INSERT INTO subscription_commercial_ledger
            (id, organization_subscription_id, entry_type, amount, currency, metadata_json, effective_at, created_by, created_at)
        SELECT gen_random_uuid(), os.id, 'opening_agreement', os.finalized_amount, 'INR',
            json_build_object('migrated_from', 'V1.1.DEV.23'), os.starts_at, os.created_by, os.created_at
        FROM organization_subscriptions os
    """)


def downgrade() -> None:
    op.drop_table("subscription_commercial_ledger")
    op.drop_table("subscription_agreement_versions")
    op.drop_index("ix_school_subscriptions_plan_id", table_name="school_subscriptions")
    op.drop_constraint("fk_school_subscriptions_plan_id", "school_subscriptions", type_="foreignkey")
    for col in ["approved_extra_capacity", "base_student_capacity", "billing_cycle", "plan_snapshot", "plan_id"]:
        op.drop_column("school_subscriptions", col)
    op.drop_index("ix_organization_subscriptions_agreement_number", table_name="organization_subscriptions")
    for col in ["agreement_accepted_at", "agreement_number", "billing_mode"]:
        op.drop_column("organization_subscriptions", col)
