from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

ACCOUNT_TYPES = {
    "SUPER_ADMIN",
    "ORGANIZATION_ADMIN",
    "SCHOOL_ADMIN",
    "ACCOUNTS",
    "TEACHER",
    "RECEPTIONIST",
    "PARENT_STUDENT",
}


class LoginRequest(BaseModel):
    account_type: str | None = Field(None, max_length=40)
    username: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    type: str
    exp: int | None = None
    school_id: str | None = None
    organization_id: str | None = None
    campus_id: str | None = None
    sid: str | None = None
    family_id: str | None = None
    is_superuser: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class UserOut(BaseModel):
    id: UUID
    username: str
    account_type: str
    email: str | None = None
    full_name: str
    designation: str | None = None
    phone: str | None = None
    is_active: bool
    is_superuser: bool
    must_change_password: bool = False
    organization_id: UUID | None = None
    school_id: UUID | None = None
    campus_id: UUID | None = None
    last_login_at: datetime | None = None
    roles: list[str] = []
    permissions: list[str] = []
    enabled_modules: list[str] = []
    model_config = {"from_attributes": True}
