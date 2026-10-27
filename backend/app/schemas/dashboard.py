from pydantic import BaseModel


class AttendanceSummary(BaseModel):
    percentage: float | None
    classes_attended: int
    total_classes: int


class MarksSummary(BaseModel):
    percentage: float | None
    label: str


class SubjectAnalytics(BaseModel):
    subject: str
    attendance_percentage: float | None
    classes_attended: int
    total_classes: int
    marks_percentage: float | None
    assessments_count: int
    attention_reasons: list[str]


class AcademicAnalytics(BaseModel):
    total_subjects: int
    subjects_with_attendance: int
    subjects_with_marks: int
    subjects_needing_attention: int
    subjects: list[SubjectAnalytics]


class ActivityItem(BaseModel):
    id: str
    title: str
    detail: str
    time: str
    category: str


class DeadlineItem(BaseModel):
    id: str
    title: str
    course: str
    due_date: str
    status: str


class DashboardResponse(BaseModel):
    attendance: AttendanceSummary
    average_marks: MarksSummary
    academic_analytics: AcademicAnalytics
    pending_assignments: int
    upcoming_exams: int | None
    recent_activity: list[ActivityItem]
    upcoming_deadlines: list[DeadlineItem]
