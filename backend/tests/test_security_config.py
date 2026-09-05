import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_shipped_example_secret():
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            secret_key="replace-with-a-random-secret-at-least-32-characters",
            database_url="postgresql+asyncpg://schoolerp:test@db:5432/schoolerp_test",
            super_admin_username="platform-owner",
            super_admin_email="platform-owner@schoolerp.test",
            super_admin_password="A-Strong-Admin-Password-123!",
            refresh_cookie_secure=True,
            cors_origins="https://erp.example.com",
            _env_file=None,
        )


def test_production_requires_secure_refresh_cookie_and_https_cors():
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            secret_key="x" * 64,
            database_url="postgresql+asyncpg://schoolerp:test@db:5432/schoolerp_test",
            super_admin_username="platform-owner",
            super_admin_email="platform-owner@schoolerp.test",
            super_admin_password="A-Strong-Admin-Password-123!",
            refresh_cookie_secure=False,
            cors_origins="http://erp.example.com",
            _env_file=None,
        )


def test_runtime_secrets_and_bootstrap_identity_are_required(monkeypatch):
    for name in (
        "SECRET_KEY",
        "DATABASE_URL",
        "SUPER_ADMIN_USERNAME",
        "SUPER_ADMIN_EMAIL",
        "SUPER_ADMIN_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    missing = {item["loc"][0] for item in exc_info.value.errors() if item["type"] == "missing"}
    assert {
        "secret_key",
        "database_url",
        "super_admin_username",
        "super_admin_email",
        "super_admin_password",
    } <= missing
