from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Assignment, AttendanceRecord, MarkRecord
from app.schemas.dashboard import DashboardResponse

ATTENDANCE_ATTENTION_THRESHOLD = 75
MARKS_ATTENTION_THRESHOLD = 70


def get_dashboard_data(db: Session, student_id: str) -> DashboardResponse:
    attendance = list(
        db.scalars(
            select(AttendanceRecord).where(
                AttendanceRecord.student_id == student_id
            )
        )
    )
    attended_classes = sum(
        record.status in ("present", "late") for record in attendance
    )
    attendance_percentage = (
        round(attended_classes / len(attendance) * 100, 2) if attendance else None
    )

    marks = list(
        db.scalars(select(MarkRecord).where(MarkRecord.student_id == student_id))
    )
    marks_possible = sum(mark.maximum_marks for mark in marks)
    marks_earned = sum(mark.marks_obtained for mark in marks)
    marks_percentage = (
        round(marks_earned / marks_possible * 100, 2) if marks_possible else None
    )

    subject_metrics: dict[str, dict[str, int | float]] = {}
    for record in attendance:
        metrics = subject_metrics.setdefault(
            record.subject,
            {
                "classes_attended": 0,
                "total_classes": 0,
                "marks_earned": 0,
                "marks_possible": 0,
                "assessments_count": 0,
            },
        )
        metrics["total_classes"] += 1
        if record.status in ("present", "late"):
            metrics["classes_attended"] += 1

    for mark in marks:
        metrics = subject_metrics.setdefault(
            mark.subject,
            {
                "classes_attended": 0,
                "total_classes": 0,
                "marks_earned": 0,
                "marks_possible": 0,
                "assessments_count": 0,
            },
        )
        metrics["marks_earned"] += mark.marks_obtained
        metrics["marks_possible"] += mark.maximum_marks
        metrics["assessments_count"] += 1

    subject_analytics = []
    for subject, metrics in sorted(subject_metrics.items()):
        total_classes = int(metrics["total_classes"])
        assessments_count = int(metrics["assessments_count"])
        subject_attendance_percentage = (
            round(int(metrics["classes_attended"]) / total_classes * 100, 2)
            if total_classes
            else None
        )
        marks_possible_for_subject = float(metrics["marks_possible"])
        subject_marks_percentage = (
            round(float(metrics["marks_earned"]) / marks_possible_for_subject * 100, 2)
            if assessments_count and marks_possible_for_subject
            else None
        )
        attention_reasons = []
        if (
            subject_attendance_percentage is not None
            and subject_attendance_percentage < ATTENDANCE_ATTENTION_THRESHOLD
        ):
            attention_reasons.append(
                f"Attendance below {ATTENDANCE_ATTENTION_THRESHOLD}%"
            )
        if (
            subject_marks_percentage is not None
            and subject_marks_percentage < MARKS_ATTENTION_THRESHOLD
        ):
            attention_reasons.append(f"Marks below {MARKS_ATTENTION_THRESHOLD}%")

        subject_analytics.append(
            {
                "subject": subject,
                "attendance_percentage": subject_attendance_percentage,
                "classes_attended": int(metrics["classes_attended"]),
                "total_classes": total_classes,
                "marks_percentage": subject_marks_percentage,
                "assessments_count": assessments_count,
                "attention_reasons": attention_reasons,
            }
        )

    assignments = list(
        db.scalars(select(Assignment).where(Assignment.student_id == student_id))
    )
    pending_assignments = sum(assignment.status == "pending" for assignment in assignments)
    upcoming_deadlines = [
        {
            "id": str(assignment.id),
            "title": assignment.title,
            "course": assignment.subject,
            "due_date": assignment.due_date.isoformat(),
            "status": (
                "overdue" if assignment.due_date < date.today() else "due"
            ),
        }
        for assignment in sorted(
            (
                assignment
                for assignment in assignments
                if assignment.status == "pending"
            ),
            key=lambda assignment: assignment.due_date,
        )
    ][:3]

    return DashboardResponse(
        attendance={
            "percentage": attendance_percentage,
            "classes_attended": attended_classes,
            "total_classes": len(attendance),
        },
        average_marks={
            "percentage": marks_percentage,
            "label": (
                f"Weighted average across {len(marks)} assessments"
                if marks
                else "No marks recorded yet"
            ),
        },
        academic_analytics={
            "total_subjects": len(subject_analytics),
            "subjects_with_attendance": sum(
                subject["total_classes"] > 0 for subject in subject_analytics
            ),
            "subjects_with_marks": sum(
                subject["assessments_count"] > 0 for subject in subject_analytics
            ),
            "subjects_needing_attention": sum(
                bool(subject["attention_reasons"]) for subject in subject_analytics
            ),
            "subjects": subject_analytics,
        },
        pending_assignments=pending_assignments,
        upcoming_exams=None,
        recent_activity=[],
        upcoming_deadlines=upcoming_deadlines,
    )
