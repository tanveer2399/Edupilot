from dataclasses import dataclass
from datetime import date, time, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core import config
from app.models.academic import Assignment, AttendanceRecord, MarkRecord, TimetableEntry
from app.models.academic_structure import StudentEnrollment
from app.models.auth import StudentAccount, UserAccount
from app.models.student import Student

ATTENDANCE_SEED = (
    ("Mathematics", date(2026, 10, 19), "present"),
    ("Mathematics", date(2026, 10, 20), "absent"),
    ("Physics", date(2026, 10, 21), "late"),
)

MARKS_SEED = (
    ("Mathematics", "Quiz 1", 8, 10, date(2026, 10, 17)),
    ("Mathematics", "Midterm", 12, 20, date(2026, 10, 22)),
    ("Physics", "Lab assessment", 18, 20, date(2026, 10, 23)),
)

TIMETABLE_SEED = (
    ("Monday", time(9, 0), time(10, 0), "Mathematics", "Room 204"),
    ("Tuesday", time(10, 0), time(11, 0), "Physics", "Lab 2"),
    ("Wednesday", time(11, 0), time(12, 0), "Mathematics", "Room 108"),
    ("Saturday", time(9, 0), time(10, 0), "Physics", "Room 312"),
)


@dataclass(frozen=True)
class SeedRecord:
    kind: str
    key_fields: tuple[str, ...]
    key: tuple[object, ...]
    values: dict[str, object]


def _expected_database_path(path: Path) -> Path:
    return path.expanduser().resolve()


def _validate_local_database(
    db: Session,
    *,
    database_url: str,
    expected_database_path: Path,
) -> dict[str, str]:
    expected_path = _expected_database_path(expected_database_path)
    if not expected_path.is_file():
        raise ValueError("The expected local SQLite database file does not exist.")
    database_paths = []
    for url_value in (database_url, str(db.get_bind().url)):
        url = make_url(url_value)
        if (
            url.drivername != "sqlite"
            or url.database in (None, "", ":memory:")
            or url.host is not None
            or url.username is not None
            or url.password is not None
            or url.port is not None
            or url.query
        ):
            raise ValueError(
                "The seed command only supports the expected local SQLite database."
            )
        resolved_path = _expected_database_path(Path(url.database))
        if resolved_path != expected_path:
            raise ValueError(
                "The configured database is not the expected local SQLite database."
            )
        database_paths.append(resolved_path)
    return {"type": "sqlite", "path": str(database_paths[0])}


def _seed_records(student_id: str) -> list[SeedRecord]:
    today = date.today()
    assignments = (
        (
            "Mathematics",
            "Practice problem set",
            "Compare the efficiency of two sorting algorithms.",
            today + timedelta(days=3),
            "pending",
        ),
        (
            "Physics",
            "Lab reflection",
            "Summarize the experiment and explain its results.",
            today - timedelta(days=2),
            "pending",
        ),
        (
            "Mathematics",
            "Submitted worksheet",
            "Review the completed worksheet.",
            today - timedelta(days=1),
            "submitted",
        ),
    )
    records = [
        SeedRecord(
            "attendance",
            ("subject", "class_date"),
            (subject, class_date),
            {
                "student_id": student_id,
                "subject": subject,
                "class_date": class_date,
                "status": status,
            },
        )
        for subject, class_date, status in ATTENDANCE_SEED
    ]
    records.extend(
        SeedRecord(
            "marks",
            ("subject", "assessment_name"),
            (subject, assessment_name),
            {
                "student_id": student_id,
                "subject": subject,
                "assessment_name": assessment_name,
                "marks_obtained": marks_obtained,
                "maximum_marks": maximum_marks,
                "assessment_date": assessment_date,
            },
        )
        for subject, assessment_name, marks_obtained, maximum_marks, assessment_date
        in MARKS_SEED
    )
    records.extend(
        SeedRecord(
            "assignments",
            ("subject", "title"),
            (subject, title),
            {
                "student_id": student_id,
                "subject": subject,
                "title": title,
                "description": description,
                "due_date": due_date,
                "status": status,
            },
        )
        for subject, title, description, due_date, status in assignments
    )
    records.extend(
        SeedRecord(
            "timetable",
            ("subject", "day_of_week", "start_time"),
            (subject, day_of_week, start_time),
            {
                "student_id": student_id,
                "subject": subject,
                "day_of_week": day_of_week,
                "start_time": start_time,
                "end_time": end_time,
                "location": location,
            },
        )
        for day_of_week, start_time, end_time, subject, location in TIMETABLE_SEED
    )
    return records


def seed_test_student_academics(
    db: Session,
    *,
    student_id: str,
    apply: bool = False,
    app_env: str | None = None,
    database_url: str | None = None,
    expected_database_path: Path | None = None,
) -> dict[str, object]:
    environment = config.APP_ENV if app_env is None else app_env
    if environment != "development":
        raise ValueError("Academic test records can only be seeded in development.")

    configured_url = config.DATABASE_URL if database_url is None else database_url
    expected_path = (
        config.BACKEND_DIR / "edupilot.db"
        if expected_database_path is None
        else expected_database_path
    )
    database = _validate_local_database(
        db,
        database_url=configured_url,
        expected_database_path=expected_path,
    )

    if not student_id or student_id != student_id.strip():
        raise ValueError("Supply the exact, non-empty student ID.")

    student = db.get(Student, student_id)
    if student is None:
        raise ValueError("The exact student ID was not found.")
    if student.is_demo:
        raise ValueError("Demo student records cannot be seeded.")

    linked_account = db.execute(
        select(StudentAccount, UserAccount)
        .join(UserAccount, UserAccount.id == StudentAccount.user_id)
        .where(StudentAccount.student_id == student_id)
    ).one_or_none()
    if (
        linked_account is None
        or linked_account[1].role != "student"
        or not linked_account[1].is_active
    ):
        raise ValueError("The student must have an active student login link.")

    active_enrollment = db.scalar(
        select(StudentEnrollment.id).where(
            StudentEnrollment.student_id == student_id,
            StudentEnrollment.status == "active",
        )
    )
    if active_enrollment is None:
        raise ValueError("The student must have an active enrollment.")

    model_by_kind = {
        "attendance": (AttendanceRecord, ("subject", "class_date")),
        "marks": (MarkRecord, ("subject", "assessment_name")),
        "assignments": (Assignment, ("subject", "title")),
        "timetable": (TimetableEntry, ("subject", "day_of_week", "start_time")),
    }
    existing_keys: dict[str, set[tuple[object, ...]]] = {}
    for kind, (model, key_fields) in model_by_kind.items():
        rows = db.execute(
            select(*(getattr(model, field) for field in key_fields)).where(
                model.student_id == student_id
            )
        )
        existing_keys[kind] = {tuple(row) for row in rows}

    records = _seed_records(student_id)
    additions = [
        record
        for record in records
        if record.key not in existing_keys[record.kind]
    ]
    skipped = len(records) - len(additions)
    counts: dict[str, dict[str, int]] = {
        kind: {
            "would_insert": sum(record.kind == kind for record in additions),
            "inserted": 0,
            "skipped": sum(
                record.kind == kind and record.key in existing_keys[kind]
                for record in records
            ),
        }
        for kind in model_by_kind
    }

    if apply and additions:
        models = {
            "attendance": AttendanceRecord,
            "marks": MarkRecord,
            "assignments": Assignment,
            "timetable": TimetableEntry,
        }
        try:
            db.add_all(
                models[record.kind](**record.values)
                for record in additions
            )
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise
        for record in additions:
            counts[record.kind]["inserted"] += 1

    return {
        "dry_run": not apply,
        "student_id": student_id,
        "student_checks": {
            "non_demo": True,
            "active_student_login_link": True,
            "active_enrollment": True,
        },
        "database": database,
        "total_would_insert": len(additions),
        "total_inserted": len(additions) if apply else 0,
        "total_skipped": skipped,
        "records": counts,
        "items": {
            kind: [
                {
                    "key": dict(zip(record.key_fields, record.key, strict=True)),
                    "status": (
                        "skipped"
                        if record.key in existing_keys[kind]
                        else "inserted"
                        if apply
                        else "would_insert"
                    ),
                }
                for record in records
                if record.kind == kind
            ]
            for kind in model_by_kind
        },
    }
