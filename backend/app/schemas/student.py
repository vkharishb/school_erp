from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class AcademicClassCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    sort_order: int | None = None


class AcademicClassUpdate(BaseModel):
    code: str | None = Field(None, min_length=1, max_length=50)
    name: str | None = Field(None, min_length=1, max_length=100)


class AcademicClassOut(AcademicClassCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    campus_id: UUID
    is_active: bool


class SectionCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)


class SectionUpdate(BaseModel):
    code: str | None = Field(None, min_length=1, max_length=50)
    name: str | None = Field(None, min_length=1, max_length=100)


class SectionOut(SectionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    academic_class_id: UUID
    is_active: bool


class SubjectCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=150)


class SubjectUpdate(BaseModel):
    code: str | None = Field(None, min_length=1, max_length=50)
    name: str | None = Field(None, min_length=1, max_length=150)


class SubjectOut(SubjectCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    campus_id: UUID
    is_active: bool


class GuardianCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    relationship_type: str = Field(min_length=2, max_length=50)
    mobile: str | None = None
    email: str | None = None
    occupation: str | None = None
    address: str | None = None
    is_primary: bool = False
    pickup_authorized: bool = False


class GuardianOut(GuardianCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class StudentCreate(BaseModel):
    campus_id: UUID | None = None
    admission_number: str = Field(min_length=1, max_length=100)
    first_name: str = Field(min_length=1, max_length=100)
    middle_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    gender: str | None = Field(None, max_length=30)
    government_id: str | None = Field(None, max_length=100)
    photo_url: str | None = None
    admission_date: date | None = None
    category: str | None = Field(None, max_length=100)
    address_line1: str | None = Field(None, max_length=255)
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = Field(None, max_length=30)
    father_name: str | None = Field(None, max_length=255)
    mother_name: str | None = Field(None, max_length=255)
    father_number: str | None = Field(None, max_length=30)
    mother_number: str | None = Field(None, max_length=30)
    email_id: EmailStr | None = None
    sub_caste: str | None = Field(None, max_length=150)
    custom_fields: dict = Field(default_factory=dict)
    guardian_ids: list[UUID] = Field(default_factory=list)
    academic_year_id: UUID | None = None
    academic_class_id: UUID | None = None
    section_id: UUID | None = None
    roll_number: str | None = None

    @model_validator(mode="after")
    def validate_enrollment(self) -> "StudentCreate":
        supplied = [self.academic_year_id, self.academic_class_id, self.section_id]
        if any(supplied) and not all(supplied):
            raise ValueError(
                "academic_year_id, academic_class_id and section_id must be supplied together"
            )
        # The new enrolment workflow has a stricter profile than legacy standalone
        # student-master creation. Enforce the mandatory enrolment fields only when
        # the Student is being created and enrolled in one operation.
        if all(supplied):
            required = {
                "date_of_birth": self.date_of_birth,
                "gender": self.gender,
                "admission_date": self.admission_date,
                "category": self.category,
                "father_name": self.father_name,
                "mother_name": self.mother_name,
                "father_number": self.father_number,
            }
            missing = [
                name.replace("_", " ").title() for name, value in required.items() if not value
            ]
            if missing:
                raise ValueError("Missing mandatory enrolment fields: " + ", ".join(missing))
        return self


class StudentUpdate(BaseModel):
    admission_number: str | None = Field(None, min_length=1, max_length=100)
    first_name: str | None = Field(None, min_length=1, max_length=100)
    middle_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    date_of_birth: date | None = None
    gender: str | None = Field(None, max_length=30)
    government_id: str | None = Field(None, max_length=100)
    photo_url: str | None = Field(None, max_length=500)
    admission_date: date | None = None
    category: str | None = Field(None, max_length=100)
    address_line1: str | None = Field(None, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    pincode: str | None = Field(None, max_length=20)
    emergency_contact_name: str | None = Field(None, max_length=255)
    emergency_contact_phone: str | None = Field(None, max_length=30)
    custom_fields: dict | None = None


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    school_id: UUID
    campus_id: UUID
    student_code: str
    admission_number: str
    first_name: str
    middle_name: str | None
    last_name: str | None
    date_of_birth: date | None
    gender: str | None
    government_id: str | None
    photo_url: str | None
    admission_date: date | None
    status: str
    category: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    pincode: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    custom_fields: dict
    created_at: datetime


class EnrollmentCreate(BaseModel):
    academic_year_id: UUID
    academic_class_id: UUID
    section_id: UUID
    roll_number: str | None = None
    enrolled_on: date


class EnrollmentOut(EnrollmentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    student_id: UUID
    status: str
