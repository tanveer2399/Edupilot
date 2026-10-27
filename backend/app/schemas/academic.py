from datetime import date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class AttendanceCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    subject: str = Field(min_length=1, max_length=120)
    class_date: date
    status: Literal["present", "absent", "late"]
    remarks: str | None = Field(default=None, max_length=500)


class AttendanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: str
    subject: str
    class_date: date
    status: Literal["present", "absent", "late"]
    remarks: str | None


class AttendanceSubjectSummary(BaseModel):
    subject: str
    present: int
    absent: int
    late: int
    total_classes: int
    percentage: float


class AttendanceSummaryResponse(BaseModel):
    total_classes: int
    classes_attended: int
    percentage: float
    subjects: list[AttendanceSubjectSummary]


class MarkCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    subject: str = Field(min_length=1, max_length=120)
    assessment_name: str = Field(min_length=1, max_length=160)
    marks_obtained: float = Field(ge=0)
    maximum_marks: float = Field(gt=0)
    assessment_date: date | None = None

    @model_validator(mode="after")
    def marks_must_not_exceed_maximum(self):
        if self.marks_obtained > self.maximum_marks:
            raise ValueError("marks_obtained cannot exceed maximum_marks")
        return self


class MarkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: str
    subject: str
    assessment_name: str
    marks_obtained: float
    maximum_marks: float
    assessment_date: date | None

    @computed_field
    @property
    def percentage(self) -> float:
        return round(self.marks_obtained / self.maximum_marks * 100, 2)


class AssignmentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    subject: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    due_date: date
    status: Literal["pending", "submitted"] = "pending"


class AssignmentResponse(BaseModel):
    id: int
    student_id: str
    subject: str
    title: str
    description: str | None
    due_date: date
    status: Literal["pending", "submitted", "overdue"]


class TimetableCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    subject: str = Field(min_length=1, max_length=120)
    day_of_week: Literal[
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
    ]
    start_time: time
    end_time: time
    location: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def end_must_follow_start(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class TimetableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: str
    subject: str
    day_of_week: str
    start_time: time
    end_time: time
    location: str | None
