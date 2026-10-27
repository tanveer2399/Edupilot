from datetime import date, time

from sqlalchemy import select

from app.core.config import AUTH_COOKIE_NAME
from app.models import (
    Assignment,
    AttendanceRecord,
    MarkRecord,
    Student,
    TimetableEntry,
)


def test_student_cannot_write_official_academic_records(client):
    requests = (
        (
            "/api/attendance",
            {
                "subject": "Computer Science",
                "class_date": "2026-10-01",
                "status": "present",
            },
        ),
        (
            "/api/marks",
            {
                "subject": "Mathematics",
                "assessment_name": "Midterm",
                "marks_obtained": 18,
                "maximum_marks": 20,
            },
        ),
        (
            "/api/assignments",
            {
                "subject": "Physics",
                "title": "Lab report",
                "due_date": "2026-10-01",
            },
        ),
        (
            "/api/timetable",
            {
                "subject": "Physics",
                "day_of_week": "Monday",
                "start_time": "09:00",
                "end_time": "10:00",
            },
        ),
    )
    for path, payload in requests:
        response = client.post(path, json=payload)
        assert response.status_code == 403


def test_unassigned_faculty_cannot_write_academic_records(auth_env):
    client = auth_env["client"]
    client.cookies.set("edupilot_session", auth_env["faculty_token"], path="/api")

    response = client.post(
        "/api/attendance",
        json={
            "subject": "Computer Science",
            "class_date": "2026-10-01",
            "status": "present",
        },
    )

    assert response.status_code == 403
    assert "class-scoped" in response.json()["detail"]


def test_academic_reads_are_scoped_to_authenticated_student(auth_env):
    client = auth_env["client"]
    with auth_env["session_factory"]() as db:
        db.add_all(
            [
                AttendanceRecord(
                    student_id="STU-TEST-0001",
                    subject="Computer Science",
                    class_date=date(2026, 10, 1),
                    status="present",
                ),
                AttendanceRecord(
                    student_id="STU-TEST-0002",
                    subject="Physics",
                    class_date=date(2026, 10, 1),
                    status="absent",
                ),
                MarkRecord(
                    student_id="STU-TEST-0001",
                    subject="Computer Science",
                    assessment_name="Quiz",
                    marks_obtained=8,
                    maximum_marks=10,
                ),
                MarkRecord(
                    student_id="STU-TEST-0002",
                    subject="Physics",
                    assessment_name="Quiz",
                    marks_obtained=2,
                    maximum_marks=10,
                ),
            ]
        )
        db.commit()

    attendance = client.get("/api/attendance")
    marks = client.get("/api/marks")
    assignments = client.get("/api/assignments")
    timetable = client.get("/api/timetable")

    assert attendance.status_code == 200
    assert [record["subject"] for record in attendance.json()] == [
        "Computer Science"
    ]
    assert marks.status_code == 200
    assert [record["subject"] for record in marks.json()] == ["Computer Science"]
    assert assignments.status_code == 200
    assert assignments.json() == []
    assert timetable.status_code == 200
    assert timetable.json() == []


def test_dashboard_calculates_metrics_from_student_records(auth_env):
    client = auth_env["client"]
    with auth_env["session_factory"]() as db:
        db.add_all(
            [
                AttendanceRecord(
                    student_id="STU-TEST-0001",
                    subject="Computer Science",
                    class_date=date(2026, 10, 1),
                    status="present",
                ),
                AttendanceRecord(
                    student_id="STU-TEST-0001",
                    subject="Computer Science",
                    class_date=date(2026, 10, 2),
                    status="absent",
                ),
                MarkRecord(
                    student_id="STU-TEST-0001",
                    subject="Computer Science",
                    assessment_name="Quiz",
                    marks_obtained=8,
                    maximum_marks=10,
                ),
            ]
        )
        db.commit()

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    dashboard = response.json()
    assert dashboard["attendance"]["percentage"] == 50.0
    assert dashboard["attendance"]["total_classes"] == 2
    assert dashboard["average_marks"]["percentage"] == 80.0


def test_each_student_dashboard_uses_only_their_own_records(auth_env):
    with auth_env["session_factory"]() as db:
        db.add_all(
            [
                AttendanceRecord(
                    student_id="STU-TEST-0001",
                    subject="Database Systems",
                    class_date=date(2026, 10, 1),
                    status="present",
                ),
                AttendanceRecord(
                    student_id="STU-TEST-0001",
                    subject="Database Systems",
                    class_date=date(2026, 10, 2),
                    status="absent",
                ),
                AttendanceRecord(
                    student_id="STU-TEST-0002",
                    subject="Physics",
                    class_date=date(2026, 10, 1),
                    status="absent",
                ),
                MarkRecord(
                    student_id="STU-TEST-0001",
                    subject="Database Systems",
                    assessment_name="Quiz",
                    marks_obtained=9,
                    maximum_marks=10,
                ),
                MarkRecord(
                    student_id="STU-TEST-0002",
                    subject="Physics",
                    assessment_name="Quiz",
                    marks_obtained=1,
                    maximum_marks=10,
                ),
                Assignment(
                    student_id="STU-TEST-0001",
                    subject="Database Systems",
                    title="Private student assignment",
                    due_date=date(2026, 10, 5),
                ),
                Assignment(
                    student_id="STU-TEST-0002",
                    subject="Physics",
                    title="Other student's assignment",
                    due_date=date(2026, 10, 5),
                ),
                TimetableEntry(
                    student_id="STU-TEST-0001",
                    subject="Database Systems",
                    day_of_week="Monday",
                    start_time=time(9, 0),
                    end_time=time(10, 0),
                    location="Room 101",
                ),
                TimetableEntry(
                    student_id="STU-TEST-0002",
                    subject="Physics",
                    day_of_week="Tuesday",
                    start_time=time(10, 0),
                    end_time=time(11, 0),
                    location="Secret Room",
                ),
            ]
        )
        db.commit()

    client = auth_env["client"]
    first_dashboard = client.get("/api/dashboard").json()
    assert first_dashboard["attendance"]["percentage"] == 50.0
    assert first_dashboard["average_marks"]["percentage"] == 90.0
    assert first_dashboard["pending_assignments"] == 1
    assert [item["subject"] for item in first_dashboard["academic_analytics"]["subjects"]] == [
        "Database Systems"
    ]
    assert [item["title"] for item in client.get("/api/assignments").json()] == [
        "Private student assignment"
    ]
    assert [item["subject"] for item in client.get("/api/timetable").json()] == [
        "Database Systems"
    ]

    client.cookies.set(
        AUTH_COOKIE_NAME,
        auth_env["other_student_token"],
        path="/api",
    )
    second_dashboard = client.get("/api/dashboard").json()
    assert second_dashboard["attendance"]["percentage"] == 0.0
    assert second_dashboard["average_marks"]["percentage"] == 10.0
    assert [item["subject"] for item in second_dashboard["academic_analytics"]["subjects"]] == [
        "Physics"
    ]
    assert [item["title"] for item in client.get("/api/assignments").json()] == [
        "Other student's assignment"
    ]
    second_timetable = client.get("/api/timetable").json()
    assert [item["subject"] for item in second_timetable] == ["Physics"]
    assert second_timetable[0]["location"] == "Secret Room"


def test_dashboard_has_explicit_empty_academic_state(client):
    response = client.get("/api/dashboard")

    assert response.status_code == 200
    dashboard = response.json()
    assert dashboard["attendance"]["percentage"] is None
    assert dashboard["attendance"]["total_classes"] == 0
    assert dashboard["average_marks"]["percentage"] is None
    assert dashboard["average_marks"]["label"] == "No marks recorded yet"
    assert dashboard["academic_analytics"]["subjects"] == []
    assert dashboard["upcoming_deadlines"] == []
    assert dashboard["recent_activity"] == []


def test_academic_records_persist_after_database_restart(tmp_path):
    database_path = tmp_path / "persistent.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import Base

    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(bind=engine, autoflush=False)
    with testing_session_local() as db:
        db.add(
            Student(
                student_id="STU-PERSIST-0001",
                full_name="Persistent Student",
                email="persist@example.edu",
                department="Computer Science",
                semester=1,
                is_demo=False,
            )
        )
        db.add(
            AttendanceRecord(
                student_id="STU-PERSIST-0001",
                subject="Computer Science",
                class_date=date(2026, 10, 21),
                status="present",
            )
        )
        db.commit()
    engine.dispose()

    restarted_engine = create_engine(
        database_url, connect_args={"check_same_thread": False}
    )
    with sessionmaker(bind=restarted_engine)() as db:
        persisted_record = db.scalar(select(AttendanceRecord))
        assert persisted_record is not None
        assert persisted_record.subject == "Computer Science"
        assert persisted_record.class_date == date(2026, 10, 21)
    restarted_engine.dispose()
