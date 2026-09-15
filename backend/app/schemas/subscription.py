from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

BillingCycle = Literal["trial", "monthly", "yearly"]
BillingModel = Literal["flat", "per_student", "tiered", "hybrid"]
DiscountType = Literal["none", "fixed", "percent"]
TaxMode = Literal["non_gst", "gst"]
BillingMode = Literal["organization", "school"]


class SubscriptionPlanBase(BaseModel):
    code: str = Field(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    plan_kind: Literal["predefined", "custom"] = "predefined"
    organization_id: UUID | None = None
    description: str | None = None
    billing_model: BillingModel = "flat"
    monthly_price: Decimal = Field(default=Decimal("0"), ge=0)
    yearly_price: Decimal = Field(default=Decimal("0"), ge=0)
    trial_days: Literal[30] = 30
    seats_included: int = Field(default=0, ge=0)
    student_limit: int = Field(default=0, ge=0)
    teacher_limit: int = Field(default=0, ge=0)
    minimum_students: int = Field(default=0, ge=0)
    excess_student_yearly_rate: Decimal = Field(default=Decimal("0"), ge=0)
    pricing_tiers: list[dict[str, Any]] = Field(default_factory=list)
    max_users: int = Field(default=50, ge=1, le=10000)
    storage_limit_mb: int = Field(default=1024, ge=0)
    enabled_modules: list[str] = Field(default_factory=list)
    addons: list[dict[str, Any]] = Field(default_factory=list)
    is_public: bool = False
    allow_overage: bool = False
    is_trial_available: bool = True
    is_popular: bool = False
    is_active: bool = True


class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass


class SubscriptionPlanUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    organization_id: UUID | None = None
    description: str | None = None
    billing_model: BillingModel | None = None
    monthly_price: Decimal | None = Field(None, ge=0)
    yearly_price: Decimal | None = Field(None, ge=0)
    trial_days: Literal[30] | None = None
    seats_included: int | None = Field(None, ge=0)
    student_limit: int | None = Field(None, ge=0)
    teacher_limit: int | None = Field(None, ge=0)
    minimum_students: int | None = Field(None, ge=0)
    excess_student_yearly_rate: Decimal | None = Field(None, ge=0)
    pricing_tiers: list[dict[str, Any]] | None = None
    max_users: int | None = Field(None, ge=1, le=10000)
    storage_limit_mb: int | None = Field(None, ge=0)
    enabled_modules: list[str] | None = None
    addons: list[dict[str, Any]] | None = None
    is_public: bool | None = None
    allow_overage: bool | None = None
    is_trial_available: bool | None = None
    is_popular: bool | None = None
    is_active: bool | None = None


class SubscriptionPlanOut(SubscriptionPlanBase):
    id: UUID
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class OrganizationSubscriptionCreate(BaseModel):
    organization_id: UUID
    plan_id: UUID
    billing_mode: BillingMode = "organization"
    billing_cycle: BillingCycle
    school_count: int = Field(ge=1, le=1000)
    discount_type: DiscountType = "none"
    discount_value: Decimal = Field(default=Decimal("0"), ge=0)
    discount_reason: str | None = None
    tax_mode: TaxMode = "non_gst"
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    activation_minimum_amount: Decimal | None = Field(None, ge=0)
    starts_at: datetime | None = None
    due_at: datetime | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_terms(self) -> "OrganizationSubscriptionCreate":
        if self.discount_type == "percent" and self.discount_value > 100:
            raise ValueError("Percentage discount cannot exceed 100")
        if self.discount_type != "none" and not (self.discount_reason or "").strip():
            raise ValueError("Discount reason is required when a discount is applied")
        if self.billing_cycle == "trial" and self.discount_value:
            raise ValueError("Trial subscriptions cannot have a discount")
        return self


class OrganizationSubscriptionUpdate(BaseModel):
    school_count: int | None = Field(None, ge=1, le=1000)
    discount_type: DiscountType | None = None
    discount_value: Decimal | None = Field(None, ge=0)
    discount_reason: str | None = None
    tax_mode: TaxMode | None = None
    tax_rate: Decimal | None = Field(None, ge=0, le=100)
    activation_minimum_amount: Decimal | None = Field(None, ge=0)
    activation_override_reason: str | None = Field(None, max_length=1000)
    due_at: datetime | None = None
    notes: str | None = None



class SubscriptionRenewalRequest(BaseModel):
    renewal_start_date: datetime
    communicated_with: str = Field(min_length=2, max_length=255)
    communication_method: Literal["phone", "email", "in_person", "whatsapp", "other"] = "phone"
    remarks: str | None = Field(None, max_length=2000)


class SubscriptionExtensionRequest(BaseModel):
    new_end_date: datetime
    reason: str = Field(min_length=3, max_length=1000)
    communicated_with: str = Field(min_length=2, max_length=255)
    communication_method: Literal["phone", "email", "in_person", "whatsapp", "other"] = "phone"
    remarks: str | None = Field(None, max_length=2000)


class TrialConversion(BaseModel):
    plan_id: UUID
    billing_cycle: Literal["monthly", "yearly"]
    school_count: int = Field(default=1, ge=1)
    discount_type: DiscountType = "none"
    discount_value: Decimal = Field(default=Decimal("0"), ge=0)
    discount_reason: str | None = None
    tax_mode: TaxMode = "non_gst"
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    activation_minimum_amount: Decimal | None = Field(None, ge=0)
    activation_override_reason: str | None = Field(None, max_length=1000)
    due_at: datetime | None = None
    notes: str | None = None


class OrganizationSubscriptionOut(BaseModel):
    id: UUID
    organization_id: UUID
    organization_name: str
    organization_code: str
    plan_id: UUID
    billing_mode: str
    agreement_number: str | None
    agreement_accepted_at: datetime | None
    plan_name: str
    billing_cycle: str
    school_count: int
    entitled_schools: int
    list_amount: Decimal
    discount_type: str
    discount_value: Decimal
    discount_amount: Decimal
    discount_reason: str | None
    tax_mode: str
    tax_rate: Decimal
    tax_amount: Decimal
    finalized_amount: Decimal
    total_received: Decimal
    balance_amount: Decimal
    activation_minimum_amount: Decimal
    activation_eligible: bool
    payment_status: str
    status: str
    starts_at: datetime
    expires_at: datetime
    grace_until: datetime | None
    last_reminder_sent_at: datetime | None = None
    due_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class SchoolSubscriptionOut(BaseModel):
    id: UUID
    school_id: UUID
    organization_subscription_id: UUID
    organization_id: UUID
    school_name: str
    school_code: str
    organization_name: str
    plan_id: UUID
    plan_name: str
    billing_cycle: str
    status: str
    starts_at: datetime
    expires_at: datetime
    days_remaining: int
    activation_status: str = "not_required"
    activation_key_masked: str | None = None
    created_at: datetime
    updated_at: datetime


class SubscriptionPaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    payment_date: datetime | None = None
    payment_mode: Literal["cash", "upi", "bank_transfer", "card", "cheque", "other"]
    reference_number: str | None = Field(None, max_length=120)
    notes: str | None = None


class SubscriptionPaymentOut(BaseModel):
    id: UUID
    organization_subscription_id: UUID
    receipt_number: str
    amount: Decimal
    payment_date: datetime
    payment_mode: str
    reference_number: str | None
    notes: str | None
    status: str
    received_by: UUID | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    tax_snapshot: dict[str, Any]
    created_at: datetime
    model_config = {"from_attributes": True}


class ActivationKeyGenerate(BaseModel):
    validity_hours: int = Field(default=72, ge=1, le=168)


class ActivationKeyGeneratedOut(BaseModel):
    id: UUID
    subscription_id: UUID
    school_id: UUID
    activation_code: str
    masked_code: str
    status: str
    valid_until: datetime


class ActivationKeyOut(BaseModel):
    id: UUID
    subscription_id: UUID
    school_id: UUID
    masked_code: str
    status: str
    valid_until: datetime
    generated_by: UUID | None
    activated_at: datetime | None
    activated_by: UUID | None
    revoked_at: datetime | None
    revocation_reason: str | None
    created_at: datetime


class ActivationRequest(BaseModel):
    school_id: UUID
    activation_code: str = Field(min_length=12, max_length=128)
    terms_accepted: bool
    terms_version: str = Field(min_length=1, max_length=64)


class ActivationTermsOut(BaseModel):
    version: str
    url: str | None = None


class ActivationResult(BaseModel):
    school_id: UUID
    subscription_id: UUID
    status: str
    plan_name: str
    activated_at: datetime
    expires_at: datetime


class OrganizationActivationSchoolOut(BaseModel):
    school_id: UUID
    school_name: str
    school_code: str
    plan_name: str
    subscription_status: str
    activation_status: str
    expires_at: datetime
    days_remaining: int


class ActivationRevoke(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class ReminderCreate(BaseModel):
    message: str | None = Field(None, max_length=2000)


class ReminderOut(BaseModel):
    id: UUID
    organization_subscription_id: UUID
    organization_admin_id: UUID
    organization_name: str
    amount_due: Decimal
    due_at: datetime | None
    channel: str
    message: str
    delivery_status: str
    sent_at: datetime
    read_at: datetime | None


class SchoolSubscriptionDisable(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)
class SubscriptionBillingSettingsUpdate(BaseModel):
    legal_name: str | None = Field(None, min_length=2, max_length=255)
    billing_address: str | None = None
    gstin: str | None = Field(None, max_length=30)
    default_tax_mode: TaxMode | None = None
    default_tax_rate: Decimal | None = Field(None, ge=0, le=100)
    gst_type: Literal["cgst_sgst", "igst"] | None = None
    receipt_prefix: str | None = Field(None, min_length=2, max_length=30)
    payment_instructions: str | None = None


class SubscriptionBillingSettingsOut(BaseModel):
    id: int
    legal_name: str
    billing_address: str | None
    gstin: str | None
    default_tax_mode: str
    default_tax_rate: Decimal
    gst_type: str
    receipt_prefix: str
    payment_instructions: str | None
    updated_by: UUID | None
    updated_at: datetime
    model_config = {"from_attributes": True}


class PlatformPaymentSummary(BaseModel):
    total_finalized: Decimal
    total_received: Decimal
    outstanding: Decimal
    overdue: Decimal
    current_month_collection: Decimal
    paid_accounts: int
    partial_accounts: int
    unpaid_accounts: int


class PaymentReceiptOut(BaseModel):
    receipt_number: str
    organization_name: str
    organization_code: str
    school_count: int
    plan_name: str
    billing_cycle: str
    amount_received: Decimal
    payment_date: datetime
    payment_mode: str
    reference_number: str | None
    tax_mode: str
    tax_rate: Decimal
    tax_amount: Decimal
    finalized_amount: Decimal
    total_received: Decimal
    balance_amount: Decimal
    issuer: SubscriptionBillingSettingsOut


class SubscriptionStatementOut(BaseModel):
    account: OrganizationSubscriptionOut
    payments: list[SubscriptionPaymentOut]
    reminders: list[ReminderOut]
    schools: list[SchoolSubscriptionOut]
