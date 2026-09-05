import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class ModuleDefinition(Base):
    """Catalog of all modules that can be licensed."""

    __tablename__ = "module_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_core: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class SchoolLicense(Base):
    """Per-school license: modules + time-bound + user limit."""

    __tablename__ = "school_licenses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), unique=True
    )

    license_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    enabled_modules: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    max_users: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    school: Mapped["School"] = relationship(back_populates="license")

    def is_valid(self) -> bool:
        now = utcnow()
        return self.is_active and self.starts_at <= now <= self.expires_at

    def has_module(self, module_code: str) -> bool:
        if not self.is_valid():
            return False
        return module_code in (self.enabled_modules or [])


from app.models.school import School  # noqa: E402
