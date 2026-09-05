from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator


class UDISECodeInput(BaseModel):
    udise_code: str = Field(min_length=2, max_length=50)
    label: str | None = Field(None, max_length=100)
    is_primary: bool = False


class UDISECodeOut(UDISECodeInput):
    id: UUID
    is_active: bool
    model_config = {"from_attributes": True}


class SchoolConfigurationBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    short_name: str | None = Field(None, max_length=50)
    area: str | None = Field(None, max_length=100)
    area_code: str | None = Field(None, min_length=2, max_length=10, pattern=r"^[A-Za-z0-9]+$")
    tagline: str | None = Field(None, max_length=255)
    principal_head_name: str | None = Field(None, max_length=255)
    principal_head_email: EmailStr | None = None
    principal_head_phone: str | None = Field(None, max_length=30)
    logo_url: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = "India"
    pincode: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    website: str | None = None
    current_academic_year: str | None = None
    academic_year_start_month: int = 4
    board: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


class SchoolConfigurationCreate(SchoolConfigurationBase):
    area: str = Field(..., min_length=2, max_length=100)


class SchoolConfigurationUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    short_name: str | None = None
    area: str | None = Field(None, min_length=2, max_length=100)
    area_code: str | None = Field(None, min_length=2, max_length=10, pattern=r"^[A-Za-z0-9]+$")
    tagline: str | None = None
    principal_head_name: str | None = None
    principal_head_email: EmailStr | None = None
    principal_head_phone: str | None = None
    logo_url: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    pincode: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    website: str | None = None
    board: str | None = None
    settings: dict[str, Any] | None = None


class SchoolConfigurationOut(SchoolConfigurationBase):
    id: UUID
    school_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class SchoolAdminCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    designation: Literal["Principal", "Headmaster", "School Administrator"]
    username: str = Field(min_length=2, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=30)
    password: str = Field(min_length=10, max_length=128)


class SchoolCreate(BaseModel):
    organization_id: UUID
    admin: SchoolAdminCreate | None = None
    configuration: SchoolConfigurationCreate
    udise_codes: list[UDISECodeInput] = Field(default_factory=list, max_length=10)
    max_users: int = Field(50, ge=1, le=10000)
    enabled_modules: list[str] = Field(default_factory=list)
    license_days: int = Field(365, ge=1, le=3650)
    license_expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_udise_primary(self) -> "SchoolCreate":
        primaries = [u for u in self.udise_codes if u.is_primary]
        if len(primaries) > 1:
            raise ValueError("Only one UDISE code can be marked Primary")
        return self


class SchoolProfileUpdate(BaseModel):
    configuration: SchoolConfigurationUpdate = Field(default_factory=SchoolConfigurationUpdate)
    udise_codes: list[UDISECodeInput] | None = Field(default=None, max_length=10)

    @model_validator(mode="after")
    def validate_udise_primary(self) -> "SchoolProfileUpdate":
        if self.udise_codes is not None and sum(1 for u in self.udise_codes if u.is_primary) > 1:
            raise ValueError("Only one UDISE code can be marked Primary")
        return self


class SchoolUpdate(BaseModel):
    is_active: bool | None = None


class SchoolOut(BaseModel):
    id: UUID
    code: str
    udise_code: str | None = None
    udise_codes: list[UDISECodeOut] = Field(default_factory=list)
    organization_id: UUID | None = None
    is_active: bool
    deleted_at: datetime | None = None
    deleted_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    configuration: SchoolConfigurationOut | None = None
    model_config = {"from_attributes": True}
