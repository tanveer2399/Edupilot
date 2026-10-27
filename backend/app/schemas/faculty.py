from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class FacultyInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class AcademicYearCreate(FacultyInput):
    name: str = Field(min_length=4, max_length=32)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def date_range_is_valid(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class AcademicYearResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    start_date: date
    end_date: date


class DepartmentCreate(FacultyInput):
    code: str = Field(min_length=2, max_length=24)
    name: str = Field(min_length=1, max_length=120)


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str


class BranchCreate(FacultyInput):
    department_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=24)
    name: str = Field(min_length=1, max_length=120)


class BranchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    department_id: int
    code: str
    name: str


class SemesterCreate(FacultyInput):
    academic_year_id: int = Field(gt=0)
    number: int = Field(gt=0, le=16)
    name: str = Field(min_length=1, max_length=64)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def date_range_is_valid(self):
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date <= self.start_date
        ):
            raise ValueError("end_date must be after start_date")
        return self


class SemesterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    academic_year_id: int
    number: int
    name: str
    start_date: date | None
    end_date: date | None


class ClassSectionCreate(FacultyInput):
    branch_id: int = Field(gt=0)
    academic_year_id: int = Field(gt=0)
    semester_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=32)


class ClassSectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    branch_id: int
    academic_year_id: int
    semester_id: int
    name: str


class SubjectCreate(FacultyInput):
    branch_id: int = Field(gt=0)
    semester_id: int = Field(gt=0)
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    credits: Decimal = Field(gt=0, max_digits=4, decimal_places=1)


class SubjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    branch_id: int
    semester_id: int
    code: str
    name: str
    credits: Decimal


class StudentCreate(FacultyInput):
    student_id: str = Field(min_length=1, max_length=32)
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    section_id: int = Field(gt=0)


class StudentUpdate(FacultyInput):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr


class FacultyStudentResponse(BaseModel):
    student_id: str
    full_name: str
    email: EmailStr
    department: str
    semester: int
    section_id: int
    section_name: str
    branch_name: str
    academic_year: str
    semester_name: str
    enrollment_status: str
    enrolled_at: datetime
