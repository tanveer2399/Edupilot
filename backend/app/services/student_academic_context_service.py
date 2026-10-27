import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, TypedDict

from sqlalchemy import case, func, select, tuple_
from sqlalchemy.orm import Session

from app.models.academic import Assignment, AttendanceRecord, MarkRecord, TimetableEntry
from app.models.academic_structure import (
    AcademicYear,
    Branch,
    ClassSection,
    Department,
    Semester,
    StudentEnrollment,
    Subject,
)
from app.models.student import Student
from app.services.dashboard_service import ATTENDANCE_ATTENTION_THRESHOLD

MAX_RECENT_ATTENDANCE = 12
MAX_MARKS_RECORDS = 30
MAX_ASSIGNMENT_RECORDS = 24
MAX_TIMETABLE_RECORDS = 20


class AcademicContext(TypedDict, total=False):
    student_profile: dict[str, Any]
    attendance: dict[str, Any]
    marks: dict[str, Any]
    assignments: dict[str, Any]
    timetable: dict[str, Any]
    academic_calendar: dict[str, Any]
    academic_summary: dict[str, Any]
    data_freshness: dict[str, str]


CONTEXT_PATTERNS: dict[str, tuple[str, ...]] = {
    "marks": (
        r"\bmarks?\b",
        r"\bgrades?\b",
        r"\bscore\b",
        r"\bexam results?\b",
        r"\bsgpa\b",
        r"\bcgpa\b",
        r"\bgpa\b",
        r"\bstrongest subject\b",
    ),
    "assignments": (
        r"\bassignments?\b",
        r"\bdeadline\b",
        r"\bdue dates?\b",
        r"\bsubmissions?\b",
        r"\boverdue\b",
        r"\bpending work\b",
    ),
    "timetable": (
        r"\btimetable\b",
        r"\bschedule\b",
        r"\bclasses today\b",
        r"\blectures?\b",
        r"\blabs?\b",
        r"\broom\b",
    ),
    "student_profile": (
        r"\bmy profile\b",
        r"\bmy subjects?\b",
        r"\bsubjects? do i take\b",
        r"\bmy semester\b",
        r"\bmy section\b",
        r"\bmy branch\b",
        r"\bmy academic year\b",
        r"\bacademic profile\b",
    ),
    "academic_calendar": (
        r"\bacademic calendar\b",
        r"\bexams?\b",
        r"\bexam schedule\b",
        r"\bacademic events?\b",
        r"\bholidays?\b",
    ),
}

ATTENDANCE_TOPIC_PATTERNS = (
    r"\battendance\b",
    r"\babsen\w*\b",
    r"\b(?:attend\w*|miss\w*)\s+classes?\b",
    r"\bclasses?\s+(?:(?:(?:have|did)\s+(?:i|we)|"
    r"(?:were|are|have been))\s+)?(?:attend\w*|miss\w*|held)\b",
)

ATTENDANCE_DATA_PATTERNS = (
    r"\b(?:percentage|rate|record|history|shortage|requirement)\b",
    r"\b(?:how many|how much|how often)\b",
    r"\b(?:show|list|display|get|check|calculate|retrieve)\b",
)

ATTENDANCE_PERSONAL_PATTERNS = (
    r"\b(?:my|mine|me|i|i'm|i've|i'd|we|our|us)\b",
)

GENERAL_ATTENDANCE_EXPLANATION_PATTERNS = (
    r"\b(?:explain|define|definition|meaning)\b",
    r"\bhow does\b.{0,60}\bwork\b",
    r"\bhow (?:is|are)\b.{0,60}\bcalculated\b",
    r"\b(?:good|normal|typical)\b.{0,40}\b(?:attendance|percentage|rate)\b",
)

FULL_CONTEXT_PATTERNS = (
    r"\boverall\s+(?:academic\s+)?performance\b",
    r"\boverall\s+(?:academic\s+)?progress\b",
    r"\bperformance\s+overall\b",
    r"\bacademic progress\b",
    r"\bacademic profile\b",
    r"\bstrengths?\b",
    r"\bweakness(?:es)?\b",
    r"\bnext semester\b",
    r"\bsummarize\b",
    r"\bcomplete profile\b",
    r"\bhow am i doing\b",
)

GENERAL_IMPROVEMENT_PATTERNS = (
    r"\bimprov(?:e|ement)\b",
    r"\bfocus on\b",
)

MARKS_COMPARISON_PATTERNS = (
    r"\b(?:performance|performing|marks?|grades?|scores?)\b.{0,60}\b"
    r"(?:compare|compared|comparison|versus|vs\.?)\b",
    r"\b(?:compare|compared|comparison|versus|vs\.?)\b.{0,60}\b"
    r"(?:performance|performing|marks?|grades?|scores?)\b",
)

MARKS_IMPROVEMENT_PATTERNS = (
    r"\b(?:improv\w*|focus\w*|work\w*|review\w*|study\w*|strengthen\w*|"
    r"raise|boost|increase)\b.{0,100}\b(?:marks?|grades?|scores?|performance|results?)\b",
    r"\b(?:marks?|grades?|scores?|performance|results?)\b.{0,100}\b"
    r"(?:improv\w*|focus\w*|work\w*|review\w*|study\w*|strengthen\w*|"
    r"raise|boost|increase)\b",
)

FOLLOW_UP_PATTERN = re.compile(
    r"\b(?:what about|how about|and|those|that|them|it|which one|why)\b",
    re.IGNORECASE,
)


def _is_attendance_question(text: str) -> bool:
    has_attendance_topic = any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in ATTENDANCE_TOPIC_PATTERNS
    )
    has_class_attendance_metric = (
        re.search(r"\b(?:percentage|rate)\b", text, re.IGNORECASE) is not None
        and re.search(r"\bclasses?\b", text, re.IGNORECASE) is not None
        and re.search(
            r"\b(?:attend\w*|absen\w*|miss\w*)\b",
            text,
            re.IGNORECASE,
        )
        is not None
    )
    if not has_attendance_topic and not has_class_attendance_metric:
        return False

    has_personal_reference = any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in ATTENDANCE_PERSONAL_PATTERNS
    )
    if has_personal_reference:
        return True

    has_data_request = any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in ATTENDANCE_DATA_PATTERNS
    )
    is_general_explanation = any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in GENERAL_ATTENDANCE_EXPLANATION_PATTERNS
    )
    return has_data_request and not is_general_explanation


def _categories_in_text(text: str) -> set[str]:
    categories = {
        category
        for category, patterns in CONTEXT_PATTERNS.items()
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)
    }
    if _is_attendance_question(text):
        categories.add("attendance")
    if any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in MARKS_COMPARISON_PATTERNS
    ):
        categories.add("marks")
    marks_improvement_question = any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in MARKS_IMPROVEMENT_PATTERNS
    )
    if marks_improvement_question:
        categories.add("marks")
    explicit_full_context = any(
        re.search(pattern, text, re.IGNORECASE) for pattern in FULL_CONTEXT_PATTERNS
    )
    general_improvement_question = not marks_improvement_question and any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in GENERAL_IMPROVEMENT_PATTERNS
    )
    if explicit_full_context or general_improvement_question:
        categories.update(
            {"student_profile", "attendance", "marks", "assignments", "timetable"}
        )
    return categories


def academic_context_categories(
    message: str,
    history: list[dict[str, str]],
) -> set[str]:
    categories = _categories_in_text(message)
    if categories:
        return categories
    if not FOLLOW_UP_PATTERN.search(message):
        return set()

    for prior in reversed(history):
        if prior.get("role") != "user":
            continue
        inherited = _categories_in_text(prior.get("content", ""))
        if inherited:
            return inherited
    return set()


def _build_profile(db: Session, student: Student) -> dict[str, Any]:
    enrollments = db.execute(
        select(
            StudentEnrollment,
            ClassSection,
            Branch,
            Department,
            Semester,
            AcademicYear,
        )
        .join(ClassSection, ClassSection.id == StudentEnrollment.section_id)
        .join(Branch, Branch.id == ClassSection.branch_id)
        .join(Department, Department.id == Branch.department_id)
        .join(Semester, Semester.id == StudentEnrollment.semester_id)
        .join(AcademicYear, AcademicYear.id == ClassSection.academic_year_id)
        .where(StudentEnrollment.student_id == student.student_id)
        .order_by(
            case((StudentEnrollment.status == "active", 0), else_=1),
            AcademicYear.start_date.desc(),
            Semester.number.desc(),
        )
        .limit(10)
    ).all()
    subject_pairs = {
        (section.branch_id, enrollment.semester_id)
        for enrollment, section, *_ in enrollments
    }
    subject_rows = []
    if subject_pairs:
        subject_rows = list(
            db.scalars(
                select(Subject)
                .where(tuple_(Subject.branch_id, Subject.semester_id).in_(subject_pairs))
                .order_by(Subject.name)
            )
        )
    subjects_by_placement: dict[tuple[int, int], list[Subject]] = {}
    for subject in subject_rows:
        placement = (subject.branch_id, subject.semester_id)
        if placement in subject_pairs:
            subjects_by_placement.setdefault(placement, []).append(subject)
    enrollment_data = []
    for enrollment, section, branch, department, semester, year in enrollments:
        subjects = subjects_by_placement.get(
            (section.branch_id, enrollment.semester_id),
            [],
        )
        enrollment_data.append(
            {
                "status": enrollment.status,
                "enrolled_at": enrollment.enrolled_at.isoformat(),
                "department": department.name,
                "branch": branch.name,
                "section": section.name,
                "academic_year": year.name,
                "semester": {
                    "number": semester.number,
                    "name": semester.name,
                },
                "registered_subjects": [
                    {
                        "name": subject.name,
                        "code": subject.code,
                        "credits": float(subject.credits),
                    }
                    for subject in subjects
                ],
            }
        )
    latest = enrollment_data[0] if enrollment_data else None
    return {
        "student_id": student.student_id,
        "name": student.full_name,
        "email": student.email,
        "department": latest["department"] if latest else student.department,
        "legacy_department": student.department,
        "legacy_semester_number": student.semester,
        "current_placement": (
            {
                "branch": latest["branch"],
                "section": latest["section"],
                "academic_year": latest["academic_year"],
                "semester": latest["semester"],
                "enrollment_status": latest["status"],
            }
            if latest
            else None
        ),
        "enrollments": enrollment_data,
        "profile_status": "available",
    }


def _build_attendance(db: Session, student_id: str) -> dict[str, Any]:
    aggregates = db.execute(
        select(
            AttendanceRecord.subject,
            func.count(AttendanceRecord.id).label("held"),
            func.sum(
                case(
                    (AttendanceRecord.status.in_(("present", "late")), 1),
                    else_=0,
                )
            ).label("attended"),
            func.sum(case((AttendanceRecord.status == "absent", 1), else_=0)).label(
                "absences"
            ),
            func.max(AttendanceRecord.class_date).label("latest_date"),
        )
        .where(AttendanceRecord.student_id == student_id)
        .group_by(AttendanceRecord.subject)
        .order_by(AttendanceRecord.subject)
    ).all()
    total_held = sum(int(row.held or 0) for row in aggregates)
    total_attended = sum(int(row.attended or 0) for row in aggregates)
    total_absences = sum(int(row.absences or 0) for row in aggregates)
    subject_wise = [
        {
            "subject": row.subject,
            "classes_attended": int(row.attended or 0),
            "classes_held": int(row.held or 0),
            "absences": int(row.absences or 0),
            "percentage": (
                round(int(row.attended or 0) / int(row.held) * 100, 2)
                if row.held
                else None
            ),
            "latest_record_date": row.latest_date.isoformat()
            if row.latest_date
            else None,
            "below_project_attention_threshold": (
                round(int(row.attended or 0) / int(row.held) * 100, 2)
                < ATTENDANCE_ATTENTION_THRESHOLD
                if row.held
                else None
            ),
        }
        for row in aggregates
    ]
    recent_records = list(
        db.scalars(
            select(AttendanceRecord)
            .where(AttendanceRecord.student_id == student_id)
            .order_by(AttendanceRecord.class_date.desc(), AttendanceRecord.id.desc())
            .limit(MAX_RECENT_ATTENDANCE)
        )
    )
    return {
        "status": "available" if total_held else "no_records",
        "calculation_basis": (
            "Present and late count as attended; absent counts as an absence. "
            "Percentage is attended recorded sessions divided by all recorded "
            "sessions. No scheduled-session data is available to identify missing "
            "attendance entries."
        ),
        "overall_percentage": (
            round(total_attended / total_held * 100, 2) if total_held else None
        ),
        "classes_attended": total_attended,
        "classes_held": total_held,
        "absences": total_absences,
        "subject_wise": subject_wise,
        "subjects_below_75_percent": [
            item["subject"]
            for item in subject_wise
            if item["below_project_attention_threshold"] is True
        ],
        "recent_history": [
            {
                "date": record.class_date.isoformat(),
                "subject": record.subject,
                "status": record.status,
            }
            for record in recent_records
        ],
        "missing_data_note": (
            "No attendance records have been entered; this is unavailable, "
            "not evidence of absence."
            if not total_held
            else None
        ),
    }


def _build_marks(db: Session, student_id: str) -> dict[str, Any]:
    aggregates = db.execute(
        select(
            MarkRecord.subject,
            func.count(MarkRecord.id).label("assessment_count"),
            func.sum(MarkRecord.marks_obtained).label("earned"),
            func.sum(MarkRecord.maximum_marks).label("possible"),
            func.max(MarkRecord.assessment_date).label("latest_date"),
        )
        .where(MarkRecord.student_id == student_id)
        .group_by(MarkRecord.subject)
        .order_by(MarkRecord.subject)
    ).all()
    total_earned = sum(float(row.earned or 0) for row in aggregates)
    total_possible = sum(float(row.possible or 0) for row in aggregates)
    subjects = [
        {
            "subject": row.subject,
            "assessments": int(row.assessment_count),
            "marks_earned": round(float(row.earned or 0), 2),
            "marks_possible": round(float(row.possible or 0), 2),
            "percentage": (
                round(float(row.earned or 0) / float(row.possible) * 100, 2)
                if row.possible
                else None
            ),
            "latest_assessment_date": row.latest_date.isoformat()
            if row.latest_date
            else None,
        }
        for row in aggregates
    ]
    ordered_subjects = sorted(
        (item for item in subjects if item["percentage"] is not None),
        key=lambda item: item["percentage"],
    )
    records = list(
        db.scalars(
            select(MarkRecord)
            .where(MarkRecord.student_id == student_id)
            .order_by(
                MarkRecord.assessment_date.desc().nullslast(),
                MarkRecord.id.desc(),
            )
            .limit(MAX_MARKS_RECORDS)
        )
    )
    return {
        "status": "available" if total_possible else "no_records",
        "calculation_basis": (
            "Overall and subject percentages are total marks earned divided by "
            "total maximum marks across all recorded assessments. Assessment "
            "names and dates are available, but no formal assessment-type field "
            "is stored."
        ),
        "topic_level_results": {
            "status": "unavailable",
            "reason": (
                "Records contain subject-level assessment totals, not "
                "question-level answers or topic-level results."
            ),
        },
        "overall_percentage": (
            round(total_earned / total_possible * 100, 2) if total_possible else None
        ),
        "assessments_recorded": sum(int(row.assessment_count) for row in aggregates),
        "subject_wise": subjects,
        "strongest_recorded_subject": ordered_subjects[-1]["subject"]
        if ordered_subjects
        else None,
        "lowest_recorded_subject": ordered_subjects[0]["subject"]
        if ordered_subjects
        else None,
        "recent_assessments": [
            {
                "subject": record.subject,
                "assessment_name": record.assessment_name,
                "marks_earned": record.marks_obtained,
                "marks_possible": record.maximum_marks,
                "percentage": round(
                    record.marks_obtained / record.maximum_marks * 100, 2
                ),
                "date": record.assessment_date.isoformat()
                if record.assessment_date
                else None,
            }
            for record in records
        ],
        "records_truncated": sum(int(row.assessment_count) for row in aggregates)
        > MAX_MARKS_RECORDS,
        "official_sgpa_cgpa": {
            "status": "unavailable",
            "reason": (
                "The database has no official grade-point results or configured "
                "credit-to-grade calculation rules."
            ),
        },
        "semester_average": {
            "status": "unavailable",
            "reason": (
                "Mark records are not linked to academic semesters, so a "
                "semester-specific average cannot be calculated."
            ),
        },
        "trend_status": (
            "per-subject assessment records are available for comparison"
            if any(row.assessment_count >= 2 for row in aggregates)
            else "insufficient historical assessments to claim a trend"
        ),
    }


def _build_assignments(db: Session, student_id: str) -> dict[str, Any]:
    today = date.today()
    status_counts = db.execute(
        select(Assignment.status, func.count(Assignment.id))
        .where(Assignment.student_id == student_id)
        .group_by(Assignment.status)
    ).all()
    counts = {status: int(count) for status, count in status_counts}
    pending = int(counts.get("pending", 0))
    submitted = int(counts.get("submitted", 0))
    overdue_count = db.scalar(
        select(func.count(Assignment.id)).where(
            Assignment.student_id == student_id,
            Assignment.status == "pending",
            Assignment.due_date < today,
        )
    ) or 0
    next_week_count = db.scalar(
        select(func.count(Assignment.id)).where(
            Assignment.student_id == student_id,
            Assignment.status == "pending",
            Assignment.due_date >= today,
            Assignment.due_date <= today + timedelta(days=7),
        )
    ) or 0
    records = list(
        db.scalars(
            select(Assignment)
            .where(Assignment.student_id == student_id)
            .order_by(Assignment.due_date, Assignment.id)
            .limit(MAX_ASSIGNMENT_RECORDS)
        )
    )
    return {
        "status": "available" if counts else "no_records",
        "counts": {
            "pending": pending,
            "submitted": submitted,
            "overdue_pending": int(overdue_count),
            "due_in_next_7_days": int(next_week_count),
            "graded": None,
        },
        "graded_status": (
            "not tracked in the current assignment model; no scores or feedback "
            "are stored."
        ),
        "upcoming_deadlines": [
            {
                "title": item.title,
                "subject": item.subject,
                "due_date": item.due_date.isoformat(),
                "status": "overdue" if item.due_date < today else "pending",
            }
            for item in records
            if item.status == "pending" and item.due_date >= today
        ][:10],
        "records": [
            {
                "title": item.title,
                "subject": item.subject,
                "due_date": item.due_date.isoformat(),
                "status": (
                    "overdue"
                    if item.status == "pending" and item.due_date < today
                    else item.status
                ),
            }
            for item in records
        ],
        "records_truncated": pending + submitted > MAX_ASSIGNMENT_RECORDS,
        "missing_data_note": (
            "No assignment records have been entered."
            if not counts
            else None
        ),
    }


def _build_timetable(db: Session, student_id: str) -> dict[str, Any]:
    entries = list(
        db.scalars(
            select(TimetableEntry)
            .where(TimetableEntry.student_id == student_id)
            .order_by(TimetableEntry.day_of_week, TimetableEntry.start_time)
            .limit(MAX_TIMETABLE_RECORDS)
        )
    )
    today_name = date.today().strftime("%A")
    return {
        "status": "available" if entries else "no_records",
        "schedule_type": "recurring weekday timetable; no dated sessions stored",
        "today": today_name,
        "todays_classes": [
            {
                "subject": entry.subject,
                "start_time": entry.start_time.strftime("%H:%M"),
                "end_time": entry.end_time.strftime("%H:%M"),
                "room": entry.location,
                "faculty": None,
            }
            for entry in entries
            if entry.day_of_week == today_name
        ],
        "weekly_schedule": [
            {
                "day": entry.day_of_week,
                "subject": entry.subject,
                "start_time": entry.start_time.strftime("%H:%M"),
                "end_time": entry.end_time.strftime("%H:%M"),
                "room": entry.location,
                "faculty": None,
            }
            for entry in entries
        ],
        "records_truncated": len(entries) >= MAX_TIMETABLE_RECORDS,
        "missing_data_note": (
            "No timetable entries have been recorded."
            if not entries
            else "Faculty names and dated upcoming sessions are not stored."
        ),
    }


def build_student_academic_context(
    db: Session,
    student: Student,
    categories: set[str],
) -> AcademicContext:
    context: AcademicContext = {
        "data_freshness": {
            "context_retrieved_at": datetime.now(timezone.utc).isoformat(),
            "reporting_date": date.today().isoformat(),
        }
    }
    if "student_profile" in categories:
        context["student_profile"] = _build_profile(db, student)
    if "attendance" in categories:
        context["attendance"] = _build_attendance(db, student.student_id)
    if "marks" in categories:
        context["marks"] = _build_marks(db, student.student_id)
    if "assignments" in categories:
        context["assignments"] = _build_assignments(db, student.student_id)
    if "timetable" in categories:
        context["timetable"] = _build_timetable(db, student.student_id)
    if "academic_calendar" in categories:
        context["academic_calendar"] = {
            "status": "unavailable",
            "reason": "No academic calendar or event model is implemented.",
        }
    if categories.issuperset(
        {"student_profile", "attendance", "marks", "assignments", "timetable"}
    ):
        attendance = context.get("attendance", {})
        marks = context.get("marks", {})
        assignments = context.get("assignments", {})
        context["academic_summary"] = {
            "attendance_percentage": attendance.get("overall_percentage"),
            "marks_percentage": marks.get("overall_percentage"),
            "official_sgpa_cgpa": marks.get("official_sgpa_cgpa"),
            "pending_assignments": assignments.get("counts", {}).get("pending"),
            "overdue_assignments": assignments.get("counts", {}).get(
                "overdue_pending"
            ),
            "attendance_attention_threshold_percent": ATTENDANCE_ATTENTION_THRESHOLD,
            "limitations": [
                "Attendance gaps cannot be distinguished without scheduled session records.",
                "No official SGPA/CGPA grading rules or final results are stored.",
                "Assignment grades and feedback are not stored.",
                "Academic calendar events are not implemented.",
            ],
        }
    return context
