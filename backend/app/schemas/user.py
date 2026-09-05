from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

ORGANIZATION_ADMIN_DESIGNATIONS = {"Secretary and Correspondent", "Chairman"}
SCHOOL_ADMIN_DESIGNATIONS = {"Principal", "Headmaster", "School Administrator"}


def validate_admin_designation(account_type: str, designation: str | None) -> str | None:
    value = designation.strip() if designation else None
    if account_type == "ORGANIZATION_ADMIN":
        value = value or "Secretary and Correspondent"
        if value not in ORGANIZATION_ADMIN_DESIGNATIONS:
            raise ValueError(
                "Organization Admin designation must be Secretary and Correspondent or Chairman"
            )
    elif account_type == "SCHOOL_ADMIN":
        value = value or "Principal"
        if value not in SCHOOL_ADMIN_DESIGNATIONS:
            raise ValueError(
                "School / Branch Admin designation must be Principal, Headmaster, or School Administrator"
            )
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
    password: str = Field(min_length=10, max_length=128)
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
        if self.account_type == "PARENT_STUDENT" and not self.phone:
            raise ValueError("Phone number is required for Parent / Student access")
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


class PasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=10, max_length=128)

    @model_validator(mode="after")
    def validate_password_content(self) -> "PasswordResetRequest":
        if not self.new_password.strip():
            raise ValueError("Password cannot be blank")
        return self


class ManagedUserOut(BaseModel):
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
