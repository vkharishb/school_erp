import re

MOBILE_RE = re.compile(r"^\d{10}$")


def normalize_india_mobile(value: str | None, *, required: bool = False) -> str | None:
    if value is None or not str(value).strip():
        if required:
            raise ValueError("Please enter a valid 10-digit mobile number.")
        return None
    raw = str(value).strip()
    if raw.startswith("+91") and len(raw) == 13 and raw[3:].isdigit():
        raw = raw[3:]
    if not MOBILE_RE.fullmatch(raw):
        raise ValueError("Please enter a valid 10-digit mobile number.")
    return f"+91{raw}"

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_email(value: str | None, *, required: bool = False) -> str | None:
    if value is None or not str(value).strip():
        if required:
            raise ValueError("Please enter a valid email address.")
        return None

    email = str(value).strip()

    if len(email) > 254 or not EMAIL_RE.fullmatch(email):
        raise ValueError("Please enter a valid email address.")

    return email

