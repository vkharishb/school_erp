"""Activation governance hardening and mandatory School parent.

Revision ID: 031
Revises: 030
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def _school_organization_fk_names() -> list[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return [
        fk["name"]
        for fk in inspector.get_foreign_keys("schools")
        if fk.get("referred_table") == "organizations"
        and fk.get("constrained_columns") == ["organization_id"]
        and fk.get("name")
    ]


def _drop_school_organization_fks() -> None:
    for name in _school_organization_fk_names():
        op.drop_constraint(name, "schools", type_="foreignkey")


def upgrade() -> None:
    # A School is never valid without a Society/Trust. Refuse to silently
    # manufacture a parent if historical orphan rows exist.
    bind = op.get_bind()
    orphan_count = bind.execute(sa.text("SELECT count(*) FROM schools WHERE organization_id IS NULL")).scalar_one()
    if orphan_count:
        raise RuntimeError(
            f"Cannot apply migration 031: {orphan_count} School row(s) have NULL organization_id. "
            "Repair those tenant records before upgrading."
        )

    _drop_school_organization_fks()
    op.alter_column("schools", "organization_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.create_foreign_key(
        "schools_organization_id_fkey",
        "schools",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.add_column("school_subscriptions", sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("school_subscriptions", sa.Column("terms_accepted_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("school_subscriptions", sa.Column("terms_version", sa.String(length=64), nullable=True))
    op.add_column("school_subscriptions", sa.Column("terms_ip_address", sa.String(length=64), nullable=True))
    op.create_foreign_key(
        "school_subscriptions_terms_accepted_by_fkey",
        "school_subscriptions",
        "users",
        ["terms_accepted_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # Existing paid Schools that have not completed activation must be closed
    # operationally. Trial remains immediately usable; already-active paid
    # entitlements remain unchanged.
    op.execute(sa.text("""
        UPDATE school_licenses sl
        SET is_active = FALSE
        FROM school_subscriptions ss, organization_subscriptions os
        WHERE ss.school_id = sl.school_id
          AND ss.organization_subscription_id = os.id
          AND os.billing_cycle <> 'trial'
          AND ss.status <> 'active'
    """))
    op.execute(sa.text("""
        UPDATE schools s
        SET is_active = FALSE
        FROM school_subscriptions ss, organization_subscriptions os
        WHERE ss.school_id = s.id
          AND ss.organization_subscription_id = os.id
          AND os.billing_cycle <> 'trial'
          AND ss.status <> 'active'
    """))


def downgrade() -> None:
    op.drop_constraint("school_subscriptions_terms_accepted_by_fkey", "school_subscriptions", type_="foreignkey")
    op.drop_column("school_subscriptions", "terms_ip_address")
    op.drop_column("school_subscriptions", "terms_version")
    op.drop_column("school_subscriptions", "terms_accepted_by")
    op.drop_column("school_subscriptions", "terms_accepted_at")

    _drop_school_organization_fks()
    op.alter_column("schools", "organization_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.create_foreign_key(
        "schools_organization_id_fkey",
        "schools",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )