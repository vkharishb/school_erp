from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TeacherCreate(BaseModel):
    campus_id: UUID
    employee_code: str = Field(min_length=1, max_length=50)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    designation: str | None = None
    qualification: str | None = None
    date_of_birth: date | None = None
    government_id: str | None = None
    category: str | None = None
    sub_category: str | None = None
    custom_fields: dict = Field(default_factory=dict)
    joining_date: date | None = None
    notes: str | None = None


class TeacherUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    designation: str | None = None
    qualification: str | None = None
    date_of_birth: date | None = None
    government_id: str | None = None
    category: str | None = None
    sub_category: str | None = None
    custom_fields: dict = Field(default_factory=dict)
    joining_date: date | None = None
    status: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class TeacherOut(TeacherCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    school_id: UUID
    user_id: UUID | None
    status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
