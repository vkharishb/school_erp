import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class SubscriptionPlan(Base):
    """Platform-owned reusable ERP subscription pack."""

    __tablename__ = "subscription_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    plan_kind: Mapped[str] = mapped_column(String(20), default="predefined", nullable=False)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    description: Mapped[str | None] = mapped_column(Text)
    billing_model: Mapped[str] = mapped_column(String(30), default="flat", nullable=False)
    monthly_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    yearly_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    trial_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    seats_included: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    student_limit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    teacher_limit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    minimum_students: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    excess_student_yearly_rate: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    pricing_tiers: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    max_users: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    storage_limit_mb: Mapped[int] = mapped_column(Integer, default=1024, nullable=False)
    enabled_modules: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    addons: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_overage: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_trial_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_popular: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class OrganizationSubscription(Base):
    """One commercial agreement and payment account for an Organization."""

    __tablename__ = "organization_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Legacy/default plan retained during Subscription V2 migration. SchoolSubscription.plan_id is authoritative.
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False
    )
    billing_mode: Mapped[str] = mapped_column(String(20), default="organization", nullable=False)
    agreement_number: Mapped[str | None] = mapped_column(String(80), unique=True, index=True)
    agreement_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    billing_cycle: Mapped[str] = mapped_column(String(20), nullable=False)
    school_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    list_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    discount_type: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    discount_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    discount_reason: Mapped[str | None] = mapped_column(Text)
    tax_mode: Mapped[str] = mapped_column(String(20), default="non_gst", nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    finalized_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total_received: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    balance_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    activation_minimum_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=0, nullable=False
    )
    activation_minimum_original: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    activation_override_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activation_override_reason: Mapped[str | None] = mapped_column(Text)
    activation_overridden_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    activation_overridden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payment_status: Mapped[str] = mapped_column(String(30), default="unpaid", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending_payment", nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class SchoolSubscription(Base):
    """Per-school entitlement under one Organization commercial agreement."""

    __tablename__ = "school_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Subscription V2 authority: each School owns its plan independently.
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    plan_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    billing_cycle: Mapped[str] = mapped_column(String(20), nullable=False)
    base_student_capacity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    approved_extra_capacity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending_activation", nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terms_accepted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    terms_version: Mapped[str | None] = mapped_column(String(64))
    terms_ip_address: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class SubscriptionPayment(Base):
    """Immutable payment-ledger entry and its receipt identity."""

    __tablename__ = "subscription_payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    receipt_number: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payment_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="received", nullable=False)
    received_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    tax_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SubscriptionActivationKey(Base):
    """One-time activation code; only a salted digest and masked suffix are retained."""

    __tablename__ = "subscription_activation_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("school_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    key_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="generated", nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    revocation_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SubscriptionPaymentReminder(Base):
    """Audited reminder addressed only to the Organization Admin."""

    __tablename__ = "subscription_payment_reminders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(20), default="in_app", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(20), default="sent", nullable=False)
    sent_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SubscriptionBillingSettings(Base):
    """Singleton platform receipt/tax configuration."""

    __tablename__ = "subscription_billing_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    legal_name: Mapped[str] = mapped_column(String(255), default="School ERP", nullable=False)
    billing_address: Mapped[str | None] = mapped_column(Text)
    gstin: Mapped[str | None] = mapped_column(String(30))
    default_tax_mode: Mapped[str] = mapped_column(String(20), default="non_gst", nullable=False)
    default_tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0, nullable=False)
    gst_type: Mapped[str] = mapped_column(String(20), default="cgst_sgst", nullable=False)
    receipt_prefix: Mapped[str] = mapped_column(String(30), default="ERP-RCPT", nullable=False)
    payment_instructions: Mapped[str | None] = mapped_column(Text)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class SubscriptionAgreementVersion(Base):
    """Immutable commercial agreement snapshot/version for an Organization subscription."""

    __tablename__ = "subscription_agreement_versions"
    __table_args__ = (UniqueConstraint("organization_subscription_id", "version_no", name="uq_subscription_agreement_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_subscription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organization_subscriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    change_type: Mapped[str] = mapped_column(String(40), default="initial", nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SubscriptionCommercialLedger(Base):
    """Append-only commercial ledger foundation for subscription financial changes."""

    __tablename__ = "subscription_commercial_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_subscription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organization_subscriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    school_subscription_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("school_subscriptions.id", ondelete="SET NULL"), index=True)
    entry_type: Mapped[str] = mapped_column(String(40), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
