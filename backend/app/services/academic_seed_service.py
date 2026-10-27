from datetime import date, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Assignment, AttendanceRecord, MarkRecord, TimetableEntry
from app.services.student_service import SAMPLE_STUDENT

SAMPLE_ATTENDANCE = [
    ("Data Structures", date(2026, 10, 5), "present"),
    ("Database Systems", date(2026, 10, 5), "present"),
    ("Operating Systems", date(2026, 10, 6), "absent"),
    ("Computer Networks", date(2026, 10, 7), "present"),
    ("Data Structures", date(2026, 10, 12), "late"),
    ("Database Systems", date(2026, 10, 12), "absent"),
    ("Operating Systems", date(2026, 10, 13), "present"),
    ("Computer Networks", date(2026, 10, 14), "present"),
]

SAMPLE_MARKS = [
    ("Data Structures", "Quiz 1", 18, 20, date(2026, 10, 8)),
    ("Database Systems", "Midterm", 42, 50, date(2026, 10, 10)),
    ("Operating Systems", "Quiz 1", 17, 20, date(2026, 10, 14)),
    ("Computer Networks", "Lab assessment", 22, 25, date(2026, 10, 16)),
]

SAMPLE_TIMETABLE = [
    ("Monday", "09:00", "10:30", "Data Structures", "Room 204"),
    ("Monday", "11:00", "12:30", "Database Systems", "Room 108"),
    ("Tuesday", "10:00", "11:30", "Operating Systems", "Room 312"),
    ("Wednesday", "09:00", "10:30", "Computer Networks", "Lab 2"),
    ("Wednesday", "11:00", "12:30", "Data Structures", "Room 204"),
    ("Thursday", "10:00", "11:30", "Database Systems", "Room 108"),
    ("Friday", "09:00", "10:30", "Operating Systems", "Room 312"),
    ("Friday", "11:00", "12:30", "Computer Networks", "Lab 2"),
]


def ensure_sample_academic_data(db: Session) -> None:
    student_id = SAMPLE_STUDENT["student_id"]

    attendance_keys = set(
        db.execute(
            select(AttendanceRecord.subject, AttendanceRecord.class_date).where(
                AttendanceRecord.student_id == student_id
            )
        ).all()
    )
    for subject, class_date, status in SAMPLE_ATTENDANCE:
        if (subject, class_date) not in attendance_keys:
            db.add(
                AttendanceRecord(
                    student_id=student_id,
                    subject=subject,
                    class_date=class_date,
                    status=status,
                )
            )

    mark_keys = set(
        db.execute(
            select(MarkRecord.subject, MarkRecord.assessment_name).where(
                MarkRecord.student_id == student_id
            )
        ).all()
    )
    for subject, assessment_name, obtained, maximum, assessment_date in SAMPLE_MARKS:
        if (subject, assessment_name) not in mark_keys:
            db.add(
                MarkRecord(
                    student_id=student_id,
                    subject=subject,
                    assessment_name=assessment_name,
                    marks_obtained=obtained,
                    maximum_marks=maximum,
                    assessment_date=assessment_date,
                )
            )

    assignment_keys = set(
        db.execute(
            select(Assignment.subject, Assignment.title).where(
                Assignment.student_id == student_id
            )
        ).all()
    )
    today = date.today()
    sample_assignments = [
        (
            "Data Structures",
            "Sorting algorithm analysis",
            "Compare the time complexity of two sorting algorithms.",
            today + timedelta(days=3),
            "pending",
        ),
        (
            "Database Systems",
            "Database schema report",
            "Document the schema and explain the key relationships.",
            today + timedelta(days=7),
            "pending",
        ),
        (
            "Operating Systems",
            "Process scheduling worksheet",
            "Work through the scheduling examples from this week's lecture.",
            today - timedelta(days=2),
            "pending",
        ),
        (
            "Computer Networks",
            "Network topology lab",
            "Submit the completed topology lab report.",
            today + timedelta(days=1),
            "submitted",
        ),
    ]
    for subject, title, description, due_date, status in sample_assignments:
        if (subject, title) not in assignment_keys:
            db.add(
                Assignment(
                    student_id=student_id,
                    subject=subject,
                    title=title,
                    description=description,
                    due_date=due_date,
                    status=status,
                )
            )

    timetable_keys = set(
        db.execute(
            select(
                TimetableEntry.subject,
                TimetableEntry.day_of_week,
                TimetableEntry.start_time,
            ).where(TimetableEntry.student_id == student_id)
        ).all()
    )
    for day, start, end, subject, location in SAMPLE_TIMETABLE:
        start_time = time.fromisoformat(start)
        key = (subject, day, start_time)
        if key not in timetable_keys:
            db.add(
                TimetableEntry(
                    student_id=student_id,
                    subject=subject,
                    day_of_week=day,
                    start_time=start_time,
                    end_time=time.fromisoformat(end),
                    location=location,
                )
            )

    db.commit()
