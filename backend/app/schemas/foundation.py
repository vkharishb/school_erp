from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    allowed_schools: int = Field(ge=1, le=999)
    head_full_name: str = Field(min_length=2, max_length=255)
    head_email: EmailStr
    head_phone: str | None = Field(None, max_length=30)
    admin_username: str = Field(min_length=2, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    admin_designation: Literal["Secretary and Correspondent", "Chairman"] = (
        "Secretary and Correspondent"
    )
    admin_email: EmailStr
    admin_password: str = Field(min_length=10, max_length=128)


class OrganizationUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    allowed_schools: int | None = Field(None, ge=1, le=999)
    head_full_name: str | None = Field(None, min_length=2, max_length=255)
    head_email: EmailStr | None = None
    head_phone: str | None = Field(None, max_length=30)


class OrganizationStatusUpdate(BaseModel):
    is_active: bool


class OrganizationLicenseUpdate(BaseModel):
    enabled_modules: list[str] | None = None
    license_expires_at: datetime | None = None


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    name: str
    allowed_schools: int
    head_full_name: str | None = None
    head_email: str | None = None
    head_phone: str | None = None
    admin_username: str | None = None
    admin_email: str | None = None
    admin_full_name: str | None = None
    admin_phone: str | None = None
    admin_designation: str | None = None
    is_active: bool
    archived_at: datetime | None = None
    archived_by: UUID | None = None
    enabled_modules: list[str]
    license_starts_at: datetime | None
    license_expires_at: datetime | None


class OrganizationDashboardUnit(BaseModel):
    school_id: UUID
    code: str
    udise_code: str | None
    name: str
    is_active: bool
    student_count: int
    teacher_count: int = 0
    today_collection: str = "0.00"
    outstanding_due: str = "0.00"
    overdue_due: str = "0.00"
    student_attendance_present: int = 0
    student_attendance_marked: int = 0
    student_attendance_percentage: float = 0
    teacher_attendance_present: int = 0
    teacher_attendance_marked: int = 0
    teacher_attendance_percentage: float = 0
    student_performance_percentage: float | None = None


class OrganizationDashboardOut(BaseModel):
    organization_id: UUID
    organization_name: str
    unit_count: int
    active_unit_count: int
    allowed_school_count: int = 0
    remaining_school_count: int = 0
    student_count: int
    teacher_count: int = 0
    as_of_date: date
    today_collection: str = "0.00"
    outstanding_due: str = "0.00"
    overdue_due: str = "0.00"
    student_attendance_present: int = 0
    student_attendance_marked: int = 0
    student_attendance_percentage: float = 0
    teacher_attendance_present: int = 0
    teacher_attendance_marked: int = 0
    teacher_attendance_percentage: float = 0
    student_performance_percentage: float | None = None
    units: list[OrganizationDashboardUnit]


class CampusCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=2, max_length=255)
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    pincode: str | None = None
    phone: str | None = None


class CampusOut(CampusCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    school_id: UUID
    is_active: bool


class AcademicYearCreate(BaseModel):
    code: str = Field(min_length=4, max_length=20, examples=["2026-27"])
    name: str = Field(min_length=2, max_length=100)
    starts_on: date
    ends_on: date
    notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "AcademicYearCreate":
        if self.ends_on <= self.starts_on:
            raise ValueError("Academic Year end date must be after start date")
        return self


class AcademicYearUpdate(BaseModel):
    code: str | None = Field(None, min_length=4, max_length=20)
    name: str | None = Field(None, min_length=2, max_length=100)
    starts_on: date | None = None
    ends_on: date | None = None
    notes: str | None = None


class OrganizationAcademicYearOut(AcademicYearCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    status: str
    is_read_only: bool
    activated_at: datetime | None
    activated_by: UUID | None


class AcademicYearOut(AcademicYearCreate):
    """Compatibility projection used internally by existing Phase-1 modules.

    Academic years are created only at Organization level in dev.3; these rows
    are generated internally so existing enrollment/fees/marks foreign keys keep
    working during Phase-1 stabilization.
    """

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    campus_id: UUID
    status: str
    is_read_only: bool
    activated_at: datetime | None
    activated_by: UUID | None


class ActivationOut(BaseModel):
    academic_year: AcademicYearOut
    previous_years_locked: int
