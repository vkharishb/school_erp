"""platform payments, organization subscriptions and school activation

Revision ID: 026
Revises: 025
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscription_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("plan_kind", sa.String(20), nullable=False, server_default="predefined"),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True)),
        sa.Column("description", sa.Text()),
        sa.Column("billing_model", sa.String(30), nullable=False, server_default="flat"),
        sa.Column("monthly_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("yearly_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("trial_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("seats_included", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_users", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("storage_limit_mb", sa.Integer(), nullable=False, server_default="1024"),
        sa.Column("enabled_modules", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("addons", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_overage", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_trial_available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_popular", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("code"),
    )
    op.create_index("ix_subscription_plans_code", "subscription_plans", ["code"])
    op.create_index("ix_subscription_plans_organization_id", "subscription_plans", ["organization_id"])

    op.create_table(
        "organization_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("billing_cycle", sa.String(20), nullable=False),
        sa.Column("school_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("list_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount_type", sa.String(20), nullable=False, server_default="none"),
        sa.Column("discount_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount_reason", sa.Text()),
        sa.Column("tax_mode", sa.String(20), nullable=False, server_default="non_gst"),
        sa.Column("tax_rate", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("finalized_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_received", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("balance_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("activation_minimum_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("payment_status", sa.String(30), nullable=False, server_default="unpaid"),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending_payment"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_organization_subscriptions_organization_id", "organization_subscriptions", ["organization_id"])
    op.create_index("ix_organization_subscriptions_due_at", "organization_subscriptions", ["due_at"])
    op.create_index("uq_organization_current_subscription", "organization_subscriptions", ["organization_id"], unique=True, postgresql_where=sa.text("status IN ('trial', 'pending_payment', 'active', 'overdue')"))

    op.create_table(
        "school_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending_activation"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_subscription_id"], ["organization_subscriptions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_school_subscriptions_school_id", "school_subscriptions", ["school_id"])
    op.create_index("ix_school_subscriptions_organization_subscription_id", "school_subscriptions", ["organization_subscription_id"])
    op.create_index("uq_school_current_subscription", "school_subscriptions", ["school_id"], unique=True, postgresql_where=sa.text("status IN ('trial', 'pending_activation', 'active', 'expiring', 'disabled')"))

    op.create_table(
        "subscription_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("receipt_number", sa.String(80), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payment_mode", sa.String(30), nullable=False),
        sa.Column("reference_number", sa.String(120)), sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="received"),
        sa.Column("received_by", postgresql.UUID(as_uuid=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_by", postgresql.UUID(as_uuid=True)),
        sa.Column("cancellation_reason", sa.Text()),
        sa.Column("tax_snapshot", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_subscription_id"], ["organization_subscriptions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["received_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cancelled_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("receipt_number"),
    )
    op.create_index("ix_subscription_payments_organization_subscription_id", "subscription_payments", ["organization_subscription_id"])
    op.create_index("ix_subscription_payments_receipt_number", "subscription_payments", ["receipt_number"])

    op.create_table(
        "subscription_activation_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False), sa.Column("key_last4", sa.String(4), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="generated"),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_by", postgresql.UUID(as_uuid=True)),
        sa.Column("activated_at", sa.DateTime(timezone=True)), sa.Column("activated_by", postgresql.UUID(as_uuid=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)), sa.Column("revoked_by", postgresql.UUID(as_uuid=True)),
        sa.Column("revocation_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["subscription_id"], ["school_subscriptions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["activated_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revoked_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("key_hash"),
    )
    op.create_index("ix_subscription_activation_keys_subscription_id", "subscription_activation_keys", ["subscription_id"])
    op.create_index("ix_subscription_activation_keys_school_id", "subscription_activation_keys", ["school_id"])

    op.create_table(
        "subscription_payment_reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False, server_default="in_app"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("delivery_status", sa.String(20), nullable=False, server_default="sent"),
        sa.Column("sent_by", postgresql.UUID(as_uuid=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["organization_subscription_id"], ["organization_subscriptions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_admin_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sent_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscription_payment_reminders_organization_subscription_id", "subscription_payment_reminders", ["organization_subscription_id"])

    op.create_table(
        "subscription_billing_settings",
        sa.Column("id", sa.Integer(), nullable=False), sa.Column("legal_name", sa.String(255), nullable=False, server_default="School ERP"),
        sa.Column("billing_address", sa.Text()), sa.Column("gstin", sa.String(30)),
        sa.Column("default_tax_mode", sa.String(20), nullable=False, server_default="non_gst"),
        sa.Column("default_tax_rate", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("gst_type", sa.String(20), nullable=False, server_default="cgst_sgst"),
        sa.Column("receipt_prefix", sa.String(30), nullable=False, server_default="ERP-RCPT"),
        sa.Column("payment_instructions", sa.Text()), sa.Column("updated_by", postgresql.UUID(as_uuid=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"),
    )
    op.execute("INSERT INTO subscription_billing_settings (id, legal_name, default_tax_mode, default_tax_rate, gst_type, receipt_prefix) VALUES (1, 'School ERP', 'non_gst', 0, 'cgst_sgst', 'ERP-RCPT')")


def downgrade() -> None:
    op.drop_table("subscription_billing_settings")
    op.drop_index("ix_subscription_payment_reminders_organization_subscription_id", table_name="subscription_payment_reminders")
    op.drop_table("subscription_payment_reminders")
    op.drop_index("ix_subscription_activation_keys_school_id", table_name="subscription_activation_keys")
    op.drop_index("ix_subscription_activation_keys_subscription_id", table_name="subscription_activation_keys")
    op.drop_table("subscription_activation_keys")
    op.drop_index("ix_subscription_payments_receipt_number", table_name="subscription_payments")
    op.drop_index("ix_subscription_payments_organization_subscription_id", table_name="subscription_payments")
    op.drop_table("subscription_payments")
    op.drop_index("uq_school_current_subscription", table_name="school_subscriptions")
    op.drop_index("ix_school_subscriptions_organization_subscription_id", table_name="school_subscriptions")
    op.drop_index("ix_school_subscriptions_school_id", table_name="school_subscriptions")
    op.drop_table("school_subscriptions")
    op.drop_index("uq_organization_current_subscription", table_name="organization_subscriptions")
    op.drop_index("ix_organization_subscriptions_due_at", table_name="organization_subscriptions")
    op.drop_index("ix_organization_subscriptions_organization_id", table_name="organization_subscriptions")
    op.drop_table("organization_subscriptions")
    op.drop_index("ix_subscription_plans_code", table_name="subscription_plans")
    op.drop_index("ix_subscription_plans_organization_id", table_name="subscription_plans")
    op.drop_table("subscription_plans")
