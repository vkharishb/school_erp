from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ModuleDefinitionOut(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None = None
    is_core: bool
    sort_order: int

    model_config = {"from_attributes": True}


class SchoolLicenseCreate(BaseModel):
    max_users: int = Field(50, ge=1, le=10000)
    enabled_modules: list[str] = Field(default_factory=list)
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    license_days: int = Field(365, ge=1, le=3650)
    notes: str | None = None


class SchoolLicenseOut(BaseModel):
    id: UUID
    school_id: UUID
    license_key: str
    enabled_modules: list[str]
    max_users: int
    starts_at: datetime
    expires_at: datetime
    is_active: bool
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    is_valid: bool = False

    model_config = {"from_attributes": True}


class SchoolLicenseUpdate(BaseModel):
    enabled_modules: list[str] | None = None
    max_users: int | None = Field(None, ge=1, le=10000)
    expires_at: datetime | None = None
    is_active: bool | None = None
    notes: str | None = None
