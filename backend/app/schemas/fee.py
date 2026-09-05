from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class FeeHeadCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=2, max_length=150)
    is_misc: bool = False


class FeeHeadOut(FeeHeadCreate):
    id: UUID
    is_active: bool
    model_config = {"from_attributes": True}


class FeeStructureCreate(BaseModel):
    campus_id: UUID
    academic_year_id: UUID
    academic_class_id: UUID | None = None
    section_id: UUID | None = None
    fee_head_id: UUID
    frequency: str = Field(min_length=2, max_length=30)
    amount: Decimal = Field(gt=0)
    due_date: date | None = None


class FeeStructureOut(FeeStructureCreate):
    id: UUID
    school_id: UUID
    is_active: bool
    model_config = {"from_attributes": True}


class ChargeCreate(BaseModel):
    student_id: UUID
    academic_year_id: UUID
    fee_head_id: UUID
    description: str = Field(min_length=2, max_length=255)
    amount: Decimal = Field(gt=0)
    due_date: date | None = None


class ChargeOut(ChargeCreate):
    id: UUID
    school_id: UUID
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


class PaymentAllocationIn(BaseModel):
    charge_id: UUID
    amount: Decimal = Field(gt=0)


class PaymentCreate(BaseModel):
    student_id: UUID
    payment_mode: str = Field(min_length=2, max_length=50)
    upi_reference_last5: str | None = Field(
        default=None, min_length=5, max_length=5, pattern=r"^[A-Za-z0-9]{5}$"
    )
    allocations: list[PaymentAllocationIn] = Field(min_length=1)


class PaymentOut(BaseModel):
    id: UUID
    student_id: UUID
    amount: Decimal
    payment_mode: str
    upi_reference_last5: str | None
    receipt_number: str
    status: str
    collected_by: UUID
    collected_at: datetime
    model_config = {"from_attributes": True}


class CancellationRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)
