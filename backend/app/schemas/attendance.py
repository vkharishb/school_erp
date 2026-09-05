from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ATTENDANCE_STATUSES = {"present", "absent", "late", "half_day", "leave"}


class AttendanceMark(BaseModel):
    entity_id: UUID
    status: str = Field(default="present")
    remarks: str | None = None


class AttendanceBulkMark(BaseModel):
    attendance_date: date
    records: list[AttendanceMark]


class StudentAttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    school_id: UUID
    campus_id: UUID
    student_id: UUID
    attendance_date: date
    status: str
    remarks: str | None
    marked_by: UUID | None
    marked_at: datetime


class TeacherAttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    school_id: UUID
    campus_id: UUID
    teacher_id: UUID
    attendance_date: date
    status: str
    remarks: str | None
    marked_by: UUID | None
    marked_at: datetime
