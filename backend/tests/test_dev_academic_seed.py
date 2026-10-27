from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (
    AcademicYear,
    Assignment,
    AttendanceRecord,
    Branch,
    ClassSection,
    Department,
    MarkRecord,
    Semester,
    Student,
    StudentAccount,
    StudentEnrollment,
    TimetableEntry,
    UserAccount,
)
from app.services.dashboard_service import get_dashboard_data
from app.services.dev_academic_seed_service import seed_test_student_academics
from app.services.student_academic_context_service import (
    build_student_academic_context,
)

TEST_STUDENT_ID = "TEST-SEED-001"
OTHER_STUDENT_ID = "TEST-SEED-002"
DEMO_STUDENT_ID = "TEST-SEED-DEMO"


@pytest.fixture
def seed_database(tmp_path):
    database_path = tmp_path / "edupilot.db"
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False)

    with session_factory() as db:
        students = [
            Student(
                student_id=TEST_STUDENT_ID,
                full_name="Seed Test Student",
                email="seed-test@example.edu",
                department="Computing",
                semester=1,
                is_demo=False,
            ),
            Student(
                student_id=OTHER_STUDENT_ID,
                full_name="Other Test Student",
                email="other-test@example.edu",
                department="Computing",
                semester=1,
                is_demo=False,
            ),
            Student(
                student_id=DEMO_STUDENT_ID,
                full_name="Demo Test Student",
                email="demo-test@example.edu",
                department="Computing",
                semester=1,
                is_demo=True,
            ),
        ]
        users = [
            UserAccount(
                id="seed-test-user",
                email="seed-user@example.edu",
                password_hash="test-only-hash",
                role="student",
                is_active=True,
            ),
            UserAccount(
                id="other-test-user",
                email="other-user@example.edu",
                password_hash="test-only-hash",
                role="student",
                is_active=True,
            ),
        ]
        users[0].student_account = StudentAccount(student_id=TEST_STUDENT_ID)
        users[1].student_account = StudentAccount(student_id=OTHER_STUDENT_ID)
        db.add_all([*students, *users])
        db.flush()

        year = AcademicYear(
            name="Test Seed Year",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=30),
            created_by_user_id=users[0].id,
        )
        department = Department(
            code="TSD",
            name="Test Seed Department",
            created_by_user_id=users[0].id,
        )
        db.add_all([year, department])
        db.flush()
        branch = Branch(
            department_id=department.id,
            code="TSB",
            name="Test Seed Branch",
            created_by_user_id=users[0].id,
        )
        db.add(branch)
        db.flush()
        semester = Semester(
            academic_year_id=year.id,
            number=1,
            name="Test Seed Semester",
            created_by_user_id=users[0].id,
        )
        db.add(semester)
        db.flush()
        section = ClassSection(
            branch_id=branch.id,
            academic_year_id=year.id,
            semester_id=semester.id,
            name="TEST",
            created_by_user_id=users[0].id,
        )
        db.add(section)
        db.flush()
        db.add(
            StudentEnrollment(
                student_id=TEST_STUDENT_ID,
                section_id=section.id,
                semester_id=semester.id,
                status="active",
            )
        )
        db.add(
            AttendanceRecord(
                student_id=DEMO_STUDENT_ID,
                subject="Demo Existing Subject",
                class_date=date(2026, 10, 18),
                status="present",
                remarks="Must remain untouched.",
            )
        )
        db.commit()

    yield database_path, session_factory, engine
    engine.dispose()


def seed(db, database_path, *, student_id=TEST_STUDENT_ID, apply=False, **kwargs):
    return seed_test_student_academics(
        db,
        student_id=student_id,
        apply=apply,
        app_env=kwargs.pop("app_env", "development"),
        database_url=kwargs.pop(
            "database_url", f"sqlite:///{database_path.as_posix()}"
        ),
        expected_database_path=kwargs.pop("expected_database_path", database_path),
        **kwargs,
    )


def record_counts(db, student_id):
    return {
        "attendance": len(
            list(
                db.scalars(
                    select(AttendanceRecord).where(
                        AttendanceRecord.student_id == student_id
                    )
                )
            )
        ),
        "marks": len(
            list(
                db.scalars(
                    select(MarkRecord).where(MarkRecord.student_id == student_id)
                )
            )
        ),
        "assignments": len(
            list(
                db.scalars(
                    select(Assignment).where(Assignment.student_id == student_id)
                )
            )
        ),
        "timetable": len(
            list(
                db.scalars(
                    select(TimetableEntry).where(
                        TimetableEntry.student_id == student_id
                    )
                )
            )
        ),
    }


def test_seed_defaults_to_read_only_dry_run(seed_database):
    database_path, session_factory, _ = seed_database

    with session_factory() as db:
        result = seed(db, database_path)

    assert result["dry_run"] is True
    assert result["total_would_insert"] == 13
    assert result["total_inserted"] == 0
    assert result["total_skipped"] == 0
    with session_factory() as db:
        assert record_counts(db, TEST_STUDENT_ID) == {
            "attendance": 0,
            "marks": 0,
            "assignments": 0,
            "timetable": 0,
        }
        demo_record = db.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.student_id == DEMO_STUDENT_ID
            )
        )
        assert demo_record.remarks == "Must remain untouched."


def test_cli_defaults_to_dry_run_on_an_isolated_database(
    seed_database,
    monkeypatch,
    capsys,
):
    import sys

    from app import cli
    from app.core import config

    database_path, session_factory, _ = seed_database
    with session_factory() as db:
        db.add(
            AttendanceRecord(
                student_id=TEST_STUDENT_ID,
                subject="Mathematics",
                class_date=date(2026, 10, 19),
                status="present",
            )
        )
        db.commit()
    monkeypatch.setattr(cli, "SessionLocal", session_factory)
    monkeypatch.setattr(config, "APP_ENV", "development")
    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    monkeypatch.setattr(config, "BACKEND_DIR", database_path.parent)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "app.cli",
            "seed-test-academics",
            "--student-id",
            TEST_STUDENT_ID,
        ],
    )

    cli.main()

    output = capsys.readouterr().out
    assert "Database type: sqlite" in output
    assert f"Database file: {database_path.resolve()}" in output
    assert f"Student ID: {TEST_STUDENT_ID}" in output
    assert (
        "Eligibility: non-demo=yes, active student login link=yes, "
        "active enrollment=yes"
    ) in output
    assert "Dry run: 12 record(s) would be inserted." in output
    assert "Inserted: 0; skipped: 1." in output
    assert "subject=Mathematics, class_date=2026-10-19: would skip" in output
    assert "subject=Mathematics, class_date=2026-10-20: would insert" in output
    assert "subject=Mathematics, assessment_name=Quiz 1: would insert" in output
    assert "subject=Mathematics, title=Practice problem set: would insert" in output
    assert (
        "subject=Mathematics, day_of_week=Monday, start_time=09:00:00: would insert"
        in output
    )
    assert "Dry-run mode made no database changes." in output
    with session_factory() as db:
        assert record_counts(db, TEST_STUDENT_ID) == {
            "attendance": 1,
            "marks": 0,
            "assignments": 0,
            "timetable": 0,
        }


def test_apply_inserts_only_for_the_explicit_student(seed_database):
    database_path, session_factory, _ = seed_database

    with session_factory() as db:
        result = seed(db, database_path, apply=True)

    assert result["dry_run"] is False
    assert result["total_inserted"] == 13
    with session_factory() as db:
        assert record_counts(db, TEST_STUDENT_ID) == {
            "attendance": 3,
            "marks": 3,
            "assignments": 3,
            "timetable": 4,
        }
        assert record_counts(db, OTHER_STUDENT_ID) == {
            "attendance": 0,
            "marks": 0,
            "assignments": 0,
            "timetable": 0,
        }
        demo_record = db.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.student_id == DEMO_STUDENT_ID
            )
        )
        assert demo_record.remarks == "Must remain untouched."


def test_apply_skips_existing_natural_keys_without_modifying_them(seed_database):
    database_path, session_factory, _ = seed_database
    original_date = date(2026, 10, 19)
    with session_factory() as db:
        existing = AttendanceRecord(
            student_id=TEST_STUDENT_ID,
            subject="Mathematics",
            class_date=original_date,
            status="absent",
            remarks="Existing record must be preserved.",
        )
        db.add(existing)
        db.commit()
        existing_id = existing.id

        result = seed(db, database_path, apply=True)

    assert result["total_inserted"] == 12
    assert result["total_skipped"] == 1
    with session_factory() as db:
        preserved = db.get(AttendanceRecord, existing_id)
        assert preserved.status == "absent"
        assert preserved.remarks == "Existing record must be preserved."


def test_rerunning_apply_is_idempotent_and_preserves_existing_values(seed_database):
    database_path, session_factory, _ = seed_database
    with session_factory() as db:
        seed(db, database_path, apply=True)
        attendance = db.scalar(
            select(AttendanceRecord).where(
                AttendanceRecord.student_id == TEST_STUDENT_ID
            )
        )
        attendance_id = attendance.id
        attendance.remarks = "Preserve this edit."
        db.commit()

    with session_factory() as db:
        result = seed(db, database_path, apply=True)
        assert result["total_inserted"] == 0
        assert result["total_skipped"] == 13
        assert record_counts(db, TEST_STUDENT_ID) == {
            "attendance": 3,
            "marks": 3,
            "assignments": 3,
            "timetable": 4,
        }
        preserved = db.get(AttendanceRecord, attendance_id)
        assert preserved.remarks == "Preserve this edit."


def test_seeded_data_populates_dashboard_and_authenticated_context(seed_database):
    database_path, session_factory, _ = seed_database
    with session_factory() as db:
        seed(db, database_path, apply=True)

    with session_factory() as db:
        dashboard = get_dashboard_data(db, TEST_STUDENT_ID)
        student = db.get(Student, TEST_STUDENT_ID)
        context = build_student_academic_context(
            db,
            student,
            {"attendance", "marks", "assignments", "timetable"},
        )

        assert dashboard.attendance.percentage == 66.67
        assert dashboard.attendance.total_classes == 3
        assert dashboard.average_marks.percentage == 76.0
        assert dashboard.pending_assignments == 2
        assert len(context["attendance"]["recent_history"]) == 3
        assert context["marks"]["assessments_recorded"] == 3
        assert context["assignments"]["counts"]["pending"] == 2
        assert len(context["timetable"]["weekly_schedule"]) == 4
        assert any(
            item["title"] == "Practice problem set"
            for item in context["assignments"]["upcoming_deadlines"]
        )


def test_seeded_records_are_isolated_from_other_student_context(seed_database):
    database_path, session_factory, _ = seed_database
    with session_factory() as db:
        seed(db, database_path, apply=True)

    with session_factory() as db:
        other_student = db.get(Student, OTHER_STUDENT_ID)
        context = build_student_academic_context(
            db,
            other_student,
            {"attendance", "marks", "assignments", "timetable"},
        )
        assert context["attendance"]["status"] == "no_records"
        assert context["marks"]["status"] == "no_records"
        assert context["assignments"]["status"] == "no_records"
        assert context["timetable"]["status"] == "no_records"
        assert record_counts(db, OTHER_STUDENT_ID) == {
            "attendance": 0,
            "marks": 0,
            "assignments": 0,
            "timetable": 0,
        }


def test_seed_rejects_non_development_and_unexpected_database(seed_database):
    database_path, session_factory, _ = seed_database
    with session_factory() as db, pytest.raises(ValueError, match="development"):
        seed(db, database_path, app_env="production")

    with session_factory() as db, pytest.raises(ValueError, match="expected local"):
        seed(
            db,
            database_path,
            expected_database_path=database_path.parent / "other.db",
        )


def test_seed_rejects_demo_student_inactive_login_and_missing_enrollment(seed_database):
    database_path, session_factory, _ = seed_database
    with session_factory() as db, pytest.raises(ValueError, match="Demo"):
        seed(db, database_path, student_id=DEMO_STUDENT_ID)

    with session_factory() as db:
        user = db.get(UserAccount, "seed-test-user")
        user.is_active = False
        db.commit()
        with pytest.raises(ValueError, match="active student login"):
            seed(db, database_path)
        user.is_active = True
        enrollment = db.scalar(
            select(StudentEnrollment).where(
                StudentEnrollment.student_id == TEST_STUDENT_ID
            )
        )
        enrollment.status = "completed"
        db.commit()
        with pytest.raises(ValueError, match="active enrollment"):
            seed(db, database_path)


def test_seed_rejects_unlinked_or_unknown_student(seed_database):
    database_path, session_factory, _ = seed_database
    with session_factory() as db, pytest.raises(ValueError, match="exact student ID"):
        seed(db, database_path, student_id="DOES-NOT-EXIST")

    with session_factory() as db:
        db.add(
            Student(
                student_id="TEST-SEED-UNLINKED",
                full_name="Unlinked Test Student",
                email="unlinked-test@example.edu",
                department="Computing",
                semester=1,
                is_demo=False,
            )
        )
        db.commit()
        with pytest.raises(ValueError, match="active student login"):
            seed(db, database_path, student_id="TEST-SEED-UNLINKED")
