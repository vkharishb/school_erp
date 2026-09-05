from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ERPAccessPolicyUpsert(BaseModel):
    organization_academic_year_id: UUID
    fee_head_id: UUID
    annual_amount: Decimal = Field(gt=0)
    is_enabled: bool = True


class ERPAccessPolicyOut(BaseModel):
    id: UUID
    school_id: UUID
    organization_academic_year_id: UUID
    fee_head_id: UUID
    annual_amount: Decimal
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ERPAccessOptIn(BaseModel):
    student_id: UUID
    access_number: str = Field(min_length=6, max_length=30)
    initial_password: str | None = Field(default=None, min_length=10, max_length=128)
    notes: str | None = Field(default=None, max_length=1000)


class ERPAccessOut(BaseModel):
    id: UUID
    school_id: UUID
    student_id: UUID
    organization_academic_year_id: UUID
    access_number: str
    status: str
    opted_by: UUID
    opted_at: datetime
    suspended_at: datetime | None
    notes: str | None
    login_account_created: bool = False
    charge_id: UUID | None = None

    model_config = {"from_attributes": True}


class AccessContactOut(BaseModel):
    mobile: str
    label: str


class LinkedStudentOut(BaseModel):
    id: UUID
    school_id: UUID
    student_code: str
    admission_number: str
    display_name: str
    status: str


class ParentStudentPortalSummary(BaseModel):
    student: dict
    enrollment: dict | None
    attendance: dict
    marks: list[dict]
    fees: dict
