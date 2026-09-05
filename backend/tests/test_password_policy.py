import pytest
from fastapi import HTTPException

from app.services.password_policy import validate_password


@pytest.mark.parametrize("password", ["password123!", "abcdefghij", "ABCDEFGHIJ", "1234567890"])
def test_weak_passwords_are_rejected(password):
    with pytest.raises(HTTPException):
        validate_password(password, username="someone")


def test_strong_password_is_accepted():
    validate_password("SchoolERP#2026Secure", username="someone")
