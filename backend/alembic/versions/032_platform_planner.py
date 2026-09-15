"""Platform Owner planner.

Revision ID: 032
Revises: 031
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_planner_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("item_type", sa.String(length=30), nullable=False, server_default="task"),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="manual"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("organization_subscription_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("school_subscription_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["completed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_subscription_id"], ["organization_subscriptions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["school_subscription_id"], ["school_subscriptions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_platform_planner_items_due_at", "platform_planner_items", ["due_at"])
    op.create_index("ix_platform_planner_items_organization_id", "platform_planner_items", ["organization_id"])
    op.create_index("ix_platform_planner_items_school_id", "platform_planner_items", ["school_id"])
    op.create_index("ix_platform_planner_items_organization_subscription_id", "platform_planner_items", ["organization_subscription_id"])
    op.create_index("ix_platform_planner_items_school_subscription_id", "platform_planner_items", ["school_subscription_id"])
    op.create_index("ix_platform_planner_items_assigned_to", "platform_planner_items", ["assigned_to"])
    op.create_index("ix_platform_planner_status_due", "platform_planner_items", ["status", "due_at"])
    op.create_index("ix_platform_planner_source_due", "platform_planner_items", ["source", "due_at"])


def downgrade() -> None:
    op.drop_index("ix_platform_planner_source_due", table_name="platform_planner_items")
    op.drop_index("ix_platform_planner_status_due", table_name="platform_planner_items")
    op.drop_index("ix_platform_planner_items_assigned_to", table_name="platform_planner_items")
    op.drop_index("ix_platform_planner_items_school_subscription_id", table_name="platform_planner_items")
    op.drop_index("ix_platform_planner_items_organization_subscription_id", table_name="platform_planner_items")
    op.drop_index("ix_platform_planner_items_school_id", table_name="platform_planner_items")
    op.drop_index("ix_platform_planner_items_organization_id", table_name="platform_planner_items")
    op.drop_index("ix_platform_planner_items_due_at", table_name="platform_planner_items")
    op.drop_table("platform_planner_items")