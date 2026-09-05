from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MarkUpsert(BaseModel):
    academic_year_id: UUID
    student_id: UUID
    subject_id: UUID
    assessment_name: str = Field(min_length=1, max_length=120)
    max_marks: Decimal = Field(gt=0)
    marks_obtained: Decimal = Field(ge=0)
    remarks: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def marks_not_over_max(self):
        if self.marks_obtained > self.max_marks:
            raise ValueError("marks_obtained cannot exceed max_marks")
        return self


class MarkOut(MarkUpsert):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    school_id: UUID
    campus_id: UUID
    is_locked: bool


class MarkLockUpdate(BaseModel):
    is_locked: bool
    reason: str | None = Field(default=None, min_length=3, max_length=500)


class MarkBulkRequest(BaseModel):
    records: list[MarkUpsert] = Field(min_length=1, max_length=1000)
