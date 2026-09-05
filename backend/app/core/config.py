from functools import lru_cache
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

KNOWN_SECRET_PLACEHOLDERS = {
    "change-this-to-a-long-random-string-in-production-min-32-chars",
    "replace-with-a-random-secret-at-least-32-characters",
    "CHANGE_ME",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    app_name: str = "SchoolERP"
    app_env: str = "development"
    debug: bool = False
    secret_key: str
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    refresh_cookie_name: str = "schoolerp_refresh"
    refresh_cookie_secure: bool = False
    auth_login_max_attempts: int = 5
    auth_login_window_seconds: int = 300

    database_url: str
    redis_url: str = "redis://redis:6379/0"

    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"

    super_admin_username: str
    super_admin_email: str
    super_admin_password: str
    super_admin_full_name: str = "Platform Super Admin"

    license_validation_interval_hours: int = 24

    backup_dir: str = "/app/backups"
    backup_schedule_hours: int = 24
    backup_retention_count: int = 30
    backup_offsite_dir: str = ""
    backup_daily_retention_days: int = 30
    backup_weekly_retention_weeks: int = 12
    backup_monthly_retention_months: int = 12
    require_recent_backup_for_archive: bool = False
    archive_backup_max_age_hours: int = 24
    browser_restore_enabled: bool = False
    pg_dump_path: str = "pg_dump"
    pg_restore_path: str = "pg_restore"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        if self.auth_login_max_attempts < 3:
            raise ValueError("AUTH_LOGIN_MAX_ATTEMPTS must be at least 3")
        if self.backup_schedule_hours < 1:
            raise ValueError("BACKUP_SCHEDULE_HOURS must be at least 1")
        if self.backup_retention_count < 1:
            raise ValueError("BACKUP_RETENTION_COUNT must be at least 1")
        if (
            self.backup_daily_retention_days < 1
            or self.backup_weekly_retention_weeks < 1
            or self.backup_monthly_retention_months < 1
        ):
            raise ValueError("Backup tier retention values must be at least 1")
        if self.archive_backup_max_age_hours < 1:
            raise ValueError("ARCHIVE_BACKUP_MAX_AGE_HOURS must be at least 1")

        if self.app_env.lower() in {"production", "prod"}:
            if len(self.secret_key) < 32 or self.secret_key in KNOWN_SECRET_PLACEHOLDERS:
                raise ValueError(
                    "A unique SECRET_KEY of at least 32 characters is required in production"
                )
            if self.super_admin_password in {
                "ChangeMeImmediately123!",
                "CHANGE_ME_BEFORE_BOOTSTRAP_123!",
            }:
                raise ValueError("SUPER_ADMIN_PASSWORD must be changed in production")
            if self.debug:
                raise ValueError("DEBUG must be false in production")
            if not self.refresh_cookie_secure:
                raise ValueError("REFRESH_COOKIE_SECURE must be true in production")
            insecure = [o for o in self.cors_origins_list if urlparse(o).scheme != "https"]
            if insecure:
                raise ValueError("Production CORS_ORIGINS must use HTTPS only")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
