from collections import defaultdict
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Assignment, AttendanceRecord, MarkRecord, Student, TimetableEntry
from app.schemas.academic import (
    AssignmentCreate,
    AssignmentResponse,
    AttendanceCreate,
    AttendanceSubjectSummary,
    MarkCreate,
    TimetableCreate,
)
from app.services.student_service import SAMPLE_STUDENT

DAY_ORDER = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}


def get_sample_student(db: Session) -> Student:
    student = db.get(Student, SAMPLE_STUDENT["student_id"])
    if student is None:
        raise HTTPException(status_code=404, detail="Sample student was not found")
    return student


def list_attendance(db: Session, student_id: str) -> list[AttendanceRecord]:
    statement = (
        select(AttendanceRecord)
        .where(AttendanceRecord.student_id == student_id)
        .order_by(AttendanceRecord.class_date.desc(), AttendanceRecord.subject)
    )
    return list(db.scalars(statement))


def summarize_attendance(
    records: list[AttendanceRecord],
) -> dict[str, object]:
    subjects: dict[str, dict[str, int]] = defaultdict(
        lambda: {"present": 0, "absent": 0, "late": 0}
    )
    for record in records:
        subjects[record.subject][record.status] += 1

    subject_summaries = []
    for subject, counts in sorted(subjects.items()):
        total = sum(counts.values())
        attended = counts["present"] + counts["late"]
        subject_summaries.append(
            AttendanceSubjectSummary(
                subject=subject,
                present=counts["present"],
                absent=counts["absent"],
                late=counts["late"],
                total_classes=total,
                percentage=round(attended / total * 100, 2),
            )
        )

    total_classes = len(records)
    classes_attended = sum(
        record.status in ("present", "late") for record in records
    )
    return {
        "total_classes": total_classes,
        "classes_attended": classes_attended,
        "percentage": (
            round(classes_attended / total_classes * 100, 2)
            if total_classes
            else 0.0
        ),
        "subjects": subject_summaries,
    }


def create_attendance(
    db: Session,
    student_id: str,
    values: AttendanceCreate,
) -> AttendanceRecord:
    existing = db.scalar(
        select(AttendanceRecord.id).where(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.subject == values.subject,
            AttendanceRecord.class_date == values.class_date,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="Attendance already exists for this subject and class date",
        )

    record = AttendanceRecord(student_id=student_id, **values.model_dump())
    db.add(record)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        duplicate = db.scalar(
            select(AttendanceRecord.id).where(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.subject == values.subject,
                AttendanceRecord.class_date == values.class_date,
            )
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=409,
                detail="Attendance already exists for this subject and class date",
            ) from error
        raise
    db.refresh(record)
    return record


def list_marks(db: Session, student_id: str) -> list[MarkRecord]:
    statement = (
        select(MarkRecord)
        .where(MarkRecord.student_id == student_id)
        .order_by(MarkRecord.assessment_date.desc(), MarkRecord.subject)
    )
    return list(db.scalars(statement))


def create_mark(db: Session, student_id: str, values: MarkCreate) -> MarkRecord:
    record = MarkRecord(student_id=student_id, **values.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def assignment_response(record: Assignment) -> AssignmentResponse:
    status = record.status
    if status == "pending" and record.due_date < date.today():
        status = "overdue"
    return AssignmentResponse(
        id=record.id,
        student_id=record.student_id,
        subject=record.subject,
        title=record.title,
        description=record.description,
        due_date=record.due_date,
        status=status,
    )


def list_assignments(db: Session, student_id: str) -> list[Assignment]:
    statement = (
        select(Assignment)
        .where(Assignment.student_id == student_id)
        .order_by(Assignment.due_date, Assignment.title)
    )
    return list(db.scalars(statement))


def get_assignment(db: Session, student_id: str, assignment_id: int) -> Assignment:
    statement = select(Assignment).where(
        Assignment.id == assignment_id,
        Assignment.student_id == student_id,
    )
    assignment = db.scalar(statement)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment


def create_assignment(
    db: Session,
    student_id: str,
    values: AssignmentCreate,
) -> Assignment:
    assignment = Assignment(student_id=student_id, **values.model_dump())
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def list_timetable(db: Session, student_id: str) -> list[TimetableEntry]:
    statement = select(TimetableEntry).where(TimetableEntry.student_id == student_id)
    entries = list(db.scalars(statement))
    return sorted(
        entries,
        key=lambda entry: (DAY_ORDER[entry.day_of_week], entry.start_time),
    )


def create_timetable_entry(
    db: Session,
    student_id: str,
    values: TimetableCreate,
) -> TimetableEntry:
    entry = TimetableEntry(student_id=student_id, **values.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
