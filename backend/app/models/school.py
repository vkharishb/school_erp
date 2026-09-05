import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.organization import Campus, Organization


def utcnow() -> datetime:
    return datetime.now(UTC)


class School(Base):
    """UDISE-registered school/campus/branch unit inside an organization."""

    __tablename__ = "schools"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    # Legacy primary UDISE mirror retained for backward compatibility; authoritative values live in school_udise_codes.
    udise_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    organization: Mapped["Organization | None"] = relationship(back_populates="schools")
    campuses: Mapped[list["Campus"]] = relationship(
        back_populates="school", cascade="all, delete-orphan"
    )
    udise_codes: Mapped[list["SchoolUDISECode"]] = relationship(
        back_populates="school", cascade="all, delete-orphan"
    )
    configuration: Mapped["SchoolConfiguration | None"] = relationship(
        back_populates="school", uselist=False, cascade="all, delete-orphan"
    )
    license: Mapped["SchoolLicense | None"] = relationship(
        back_populates="school", uselist=False, cascade="all, delete-orphan"
    )
    users: Mapped[list["User"]] = relationship(
        back_populates="school", foreign_keys="User.school_id"
    )

    __table_args__ = (
        # ERP business code is permanent and scoped to the owning organization.
        Index(
            "ix_schools_org_code",
            "organization_id",
            "code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


class SchoolUDISECode(Base):
    """Optional one-to-many UDISE identifiers for a school/branch."""

    __tablename__ = "school_udise_codes"
    __table_args__ = (
        Index(
            "ix_school_udise_active_unique",
            "udise_code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND is_active IS TRUE"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    udise_code: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str | None] = mapped_column(String(100))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    school: Mapped["School"] = relationship(back_populates="udise_codes")


class SchoolConfiguration(Base):
    """Configuration for one UDISE-registered campus/school/branch unit."""

    __tablename__ = "school_configurations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), unique=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(50))
    area: Mapped[str | None] = mapped_column(String(100))
    area_code: Mapped[str | None] = mapped_column(String(10))
    tagline: Mapped[str | None] = mapped_column(String(255))
    principal_head_name: Mapped[str | None] = mapped_column(String(255))
    principal_head_email: Mapped[str | None] = mapped_column(String(255))
    principal_head_phone: Mapped[str | None] = mapped_column(String(30))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    address_line1: Mapped[str | None] = mapped_column(String(255))
    address_line2: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100), default="India")
    pincode: Mapped[str | None] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255))
    website: Mapped[str | None] = mapped_column(String(255))

    current_academic_year: Mapped[str | None] = mapped_column(String(20))
    academic_year_start_month: Mapped[int] = mapped_column(default=4)
    board: Mapped[str | None] = mapped_column(String(100))

    settings: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    school: Mapped["School"] = relationship(back_populates="configuration")


from app.models.license import SchoolLicense  # noqa: E402
from app.models.user import User  # noqa: E402
