from app.schemas.auth import LoginRequest, Token, TokenPayload, UserOut
from app.schemas.license import ModuleDefinitionOut, SchoolLicenseCreate, SchoolLicenseOut
from app.schemas.school import (
    SchoolConfigurationCreate,
    SchoolConfigurationOut,
    SchoolConfigurationUpdate,
    SchoolCreate,
    SchoolOut,
    SchoolUpdate,
)

__all__ = [
    "LoginRequest",
    "ModuleDefinitionOut",
    "SchoolConfigurationCreate",
    "SchoolConfigurationOut",
    "SchoolConfigurationUpdate",
    "SchoolCreate",
    "SchoolLicenseCreate",
    "SchoolLicenseOut",
    "SchoolOut",
    "SchoolUpdate",
    "Token",
    "TokenPayload",
    "UserOut",
]
