import re

from fastapi import HTTPException

COMMON_PASSWORDS = {
    "password",
    "password123",
    "password123!",
    "1234567890",
    "qwerty12345",
    "admin12345",
    "welcome123",
    "changeme123!",
    "schoolerp123!",
}


def validate_password(password: str, *, username: str | None = None) -> None:
    if len(password) < 10 or len(password) > 128:
        raise HTTPException(status_code=422, detail="Password must be 10 to 128 characters")
    if not password.strip():
        raise HTTPException(status_code=422, detail="Password cannot be blank")
    if username and password.casefold() == username.casefold():
        raise HTTPException(status_code=422, detail="Password must not be the same as the username")
    if password.casefold() in COMMON_PASSWORDS:
        raise HTTPException(status_code=422, detail="Password is too common")
    checks = [r"[A-Z]", r"[a-z]", r"[0-9]", r"[^A-Za-z0-9]"]
    if sum(bool(re.search(pattern, password)) for pattern in checks) < 3:
        raise HTTPException(
            status_code=422,
            detail="Password must use at least three of uppercase, lowercase, number and symbol",
        )
