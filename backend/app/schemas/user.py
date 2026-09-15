from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.core.contact_validation import normalize_email, normalize_india_mobile

ORGANIZATION_ADMIN_DESIGNATIONS = {
    "Chairman",
    "Secretary & Correspondent",
    "Treasurer",
    "Director",
    "Managing Director",
    "Administrator",
    "Authorized Representative",
}
SCHOOL_ADMIN_DESIGNATIONS = {"Principal", "Headmaster", "School Administrator"}


def validate_admin_designation(account_type: str, designation: str | None) -> str | None:
    value = designation.strip() if designation else None
    if account_type == "ORGANIZATION_ADMIN":
        if not value or value not in ORGANIZATION_ADMIN_DESIGNATIONS:
            raise ValueError(
                "Organization Admin designation must be Chairman, Secretary & Correspondent, "
                "Treasurer, Director, Managing Director, Administrator, or Authorized Representative"
            )
        return value
    if account_type == "SCHOOL_ADMIN":
        value = value or "Principal"
        if value not in SCHOOL_ADMIN_DESIGNATIONS:
            raise ValueError("School / Branch Admin designation must be Principal, Headmaster, or School Administrator")
    return value


PREDEFINED_ACCOUNT_TYPES = {
    "SUPER_ADMIN",
    "ORGANIZATION_ADMIN",
    "SCHOOL_ADMIN",
    "ACCOUNTS",
    "TEACHER",
    "RECEPTIONIST",
    "PARENT_STUDENT",
}


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    full_name: str = Field(min_length=2, max_length=255)
    designation: str | None = Field(None, max_length=100)
    account_type: str
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=30)
    organization_id: UUID | None = None
    school_id: UUID | None = None
    campus_id: UUID | None = None
    role_codes: list[str] | None = None

    @model_validator(mode="after")
    def validate_scope_order(self) -> "UserCreate":
        if self.account_type not in PREDEFINED_ACCOUNT_TYPES:
            raise ValueError("Unknown account type")
        self.designation = validate_admin_designation(self.account_type, self.designation)
        if self.account_type in {"SCHOOL_ADMIN", "ACCOUNTS", "TEACHER", "RECEPTIONIST", "PARENT_STUDENT"}:
            if not self.email:
                raise ValueError("Email is required for school-level users")
            if not self.phone:
                raise ValueError("Phone is required for school-level users")
        if self.email is not None:
            self.email = normalize_email(str(self.email), required=True)
        if self.phone is not None:
            self.phone = normalize_india_mobile(self.phone, required=True)
        if self.campus_id and not self.school_id:
            raise ValueError("school_id is required when campus_id is supplied")
        if self.school_id and not self.organization_id:
            raise ValueError("organization_id is required when school_id is supplied")
        return self


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=255)
    designation: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=30)
    is_active: bool | None = None
    role_codes: list[str] | None = Field(None, min_length=1)

    @model_validator(mode="after")
    def validate_contacts(self) -> "UserUpdate":
        if self.email is not None:
            self.email = normalize_email(str(self.email), required=True)
        if self.phone is not None:
            self.phone = normalize_india_mobile(self.phone, required=True)
        return self


class PasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=10, max_length=128)

    @model_validator(mode="after")
    def validate_password_content(self) -> "PasswordResetRequest":
        if not self.new_password.strip():
            raise ValueError("Password cannot be blank")
        return self


class ManagedUserOut(BaseModel):
    temporary_password: str | None = None
    id: UUID
    username: str
    account_type: str
    email: str | None
    full_name: str
    designation: str | None = None
    phone: str | None
    is_active: bool
    is_superuser: bool
    must_change_password: bool = False
    organization_id: UUID | None
    school_id: UUID | None
    campus_id: UUID | None
    last_login_at: datetime | None
    roles: list[str]


