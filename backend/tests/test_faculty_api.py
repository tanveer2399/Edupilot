from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select

from app.core.config import AUTH_COOKIE_NAME
from app.models.academic_structure import (
    AcademicYear,
    StudentEnrollment,
)
from app.core.config import BACKEND_DIR
from app.core.security import create_session_token, hash_session_token, hash_password
from app.models.auth import AuthSession, FacultyAccount, UserAccount
from app.models.student import Student


@pytest.fixture
def faculty_client(auth_env):
    client = auth_env["client"]
    client.cookies.set(
        AUTH_COOKIE_NAME,
        auth_env["faculty_token"],
        path="/api",
    )
    return client


def create_structure(client):
    year_response = client.post(
        "/api/faculty/academic-years",
        json={
            "name": "2026-27",
            "start_date": "2026-07-01",
            "end_date": "2027-06-30",
        },
    )
    assert year_response.status_code == 201
    department_response = client.post(
        "/api/faculty/departments",
        json={"code": "cse", "name": "Computer Science"},
    )
    assert department_response.status_code == 201
    branch_response = client.post(
        "/api/faculty/branches",
        json={
            "department_id": department_response.json()["id"],
            "code": "AIML",
            "name": "Artificial Intelligence",
        },
    )
    assert branch_response.status_code == 201
    semester_response = client.post(
        "/api/faculty/semesters",
        json={
            "academic_year_id": year_response.json()["id"],
            "number": 1,
            "name": "Semester 1",
            "start_date": "2026-07-01",
            "end_date": "2026-12-20",
        },
    )
    assert semester_response.status_code == 201
    section_response = client.post(
        "/api/faculty/sections",
        json={
            "branch_id": branch_response.json()["id"],
            "academic_year_id": year_response.json()["id"],
            "semester_id": semester_response.json()["id"],
            "name": "A",
        },
    )
    assert section_response.status_code == 201
    return {
        "year": year_response.json(),
        "department": department_response.json(),
        "branch": branch_response.json(),
        "semester": semester_response.json(),
        "section": section_response.json(),
    }


def test_faculty_can_create_and_read_owned_academic_structure(faculty_client):
    structure = create_structure(faculty_client)

    subject = faculty_client.post(
        "/api/faculty/subjects",
        json={
            "branch_id": structure["branch"]["id"],
            "semester_id": structure["semester"]["id"],
            "code": "ai101",
            "name": "Introduction to AI",
            "credits": 3.0,
        },
    )

    assert subject.status_code == 201
    assert subject.json()["code"] == "AI101"
    assert subject.json()["credits"] == "3.0"
    assert len(faculty_client.get("/api/faculty/academic-years").json()) == 1
    assert len(faculty_client.get("/api/faculty/departments").json()) == 1
    assert len(faculty_client.get("/api/faculty/branches").json()) == 1
    assert len(faculty_client.get("/api/faculty/semesters").json()) == 1
    assert len(faculty_client.get("/api/faculty/sections").json()) == 1
    assert len(faculty_client.get("/api/faculty/subjects").json()) == 1


def test_faculty_can_create_enrolled_student_and_update_profile(
    faculty_client,
    auth_env,
):
    structure = create_structure(faculty_client)
    created = faculty_client.post(
        "/api/faculty/students",
        json={
            "student_id": "STU-ENROLLED-01",
            "full_name": "Enrolled Learner",
            "email": "enrolled@example.edu",
            "section_id": structure["section"]["id"],
        },
    )

    assert created.status_code == 201
    assert created.json()["department"] == "Artificial Intelligence"
    assert created.json()["semester"] == 1
    assert created.json()["section_name"] == "A"
    assert created.json()["academic_year"] == "2026-27"
    assert created.json()["enrollment_status"] == "active"
    assert [item["student_id"] for item in faculty_client.get("/api/faculty/students").json()] == [
        "STU-ENROLLED-01"
    ]

    updated = faculty_client.patch(
        "/api/faculty/students/STU-ENROLLED-01",
        json={"full_name": "Updated Learner", "email": "updated@example.edu"},
    )
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Updated Learner"

    with auth_env["session_factory"]() as db:
        student = db.get(Student, "STU-ENROLLED-01")
        enrollment = db.scalar(
            select(StudentEnrollment).where(
                StudentEnrollment.student_id == "STU-ENROLLED-01"
            )
        )
        assert student.email == "updated@example.edu"
        assert student.is_demo is False
        assert enrollment is not None
        assert enrollment.section_id == structure["section"]["id"]


def test_student_cannot_access_faculty_management_or_write_records(client):
    response = client.get("/api/faculty/students")
    create_response = client.post(
        "/api/faculty/departments",
        json={"code": "CSE", "name": "Computer Science"},
    )

    assert response.status_code == 403
    assert create_response.status_code == 403


def test_faculty_cannot_reference_another_faculty_academic_records(
    faculty_client,
    auth_env,
):
    structure = create_structure(faculty_client)
    created_student = faculty_client.post(
        "/api/faculty/students",
        json={
            "student_id": "STU-PRIVATE-01",
            "full_name": "Private Student",
            "email": "private@example.edu",
            "section_id": structure["section"]["id"],
        },
    )
    assert created_student.status_code == 201
    second_faculty_token = create_session_token()
    second_faculty_id = str(uuid4())
    with auth_env["session_factory"]() as db:
        other_faculty = UserAccount(
            id=second_faculty_id,
            email="other-faculty@example.edu",
            password_hash=hash_password("Other-Faculty-Password-12"),
            role="faculty",
        )
        other_faculty.faculty_account = FacultyAccount(
            faculty_code="FAC-OTHER",
            full_name="Other Faculty",
        )
        other_faculty.sessions.append(
            AuthSession(
                id=str(uuid4()),
                token_hash=hash_session_token(second_faculty_token),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        db.add(other_faculty)
        db.commit()

    faculty_client.cookies.set(
        AUTH_COOKIE_NAME,
        second_faculty_token,
        path="/api",
    )

    assert faculty_client.get("/api/faculty/academic-years").json() == []
    denied_branch = faculty_client.post(
        "/api/faculty/sections",
        json={
            "branch_id": structure["branch"]["id"],
            "academic_year_id": structure["year"]["id"],
            "semester_id": structure["semester"]["id"],
            "name": "B",
        },
    )
    assert denied_branch.status_code == 404
    denied_update = faculty_client.patch(
        "/api/faculty/students/STU-PRIVATE-01",
        json={"full_name": "Unauthorized Change", "email": "hack@example.edu"},
    )
    assert denied_update.status_code == 404


def test_section_rejects_semester_from_a_different_academic_year(faculty_client):
    structure = create_structure(faculty_client)
    another_year = faculty_client.post(
        "/api/faculty/academic-years",
        json={
            "name": "2027-28",
            "start_date": "2027-07-01",
            "end_date": "2028-06-30",
        },
    )
    assert another_year.status_code == 201

    response = faculty_client.post(
        "/api/faculty/sections",
        json={
            "branch_id": structure["branch"]["id"],
            "academic_year_id": another_year.json()["id"],
            "semester_id": structure["semester"]["id"],
            "name": "B",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "The semester must belong to the selected academic year."


def test_academic_structure_migration_tables_exist(tmp_path):
    database_path = tmp_path / "stage1-persistence.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    migration_config = Config(str(BACKEND_DIR / "alembic.ini"))
    migration_config.attributes["database_url"] = database_url
    migration_config.attributes["configure_logger"] = False
    command.upgrade(migration_config, "head")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine)
    faculty_id = str(uuid4())
    with factory() as db:
        faculty = UserAccount(
            id=faculty_id,
            email="migration-faculty@example.edu",
            password_hash=hash_password("Migration-Faculty-Password-12"),
            role="faculty",
        )
        faculty.faculty_account = FacultyAccount(
            faculty_code="FAC-MIGRATION",
            full_name="Migration Faculty",
        )
        db.add(faculty)
        db.flush()
        db.add(
            AcademicYear(
                name="2099-2100",
                start_date=date(2099, 7, 1),
                end_date=date(2100, 6, 30),
                created_by_user_id=faculty_id,
            )
        )
        db.commit()
    engine.dispose()

    restarted_engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )
    with sessionmaker(bind=restarted_engine)() as db:
        persisted = db.scalar(
            select(AcademicYear).where(AcademicYear.name == "2099-2100")
        )
        assert persisted is not None
        assert persisted.start_date == date(2099, 7, 1)
    restarted_engine.dispose()


def test_migration_preserves_existing_legacy_student_and_attendance_rows(tmp_path):
    database_path = tmp_path / "legacy-data.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE students ("
                "student_id VARCHAR(32) PRIMARY KEY, "
                "full_name VARCHAR(120) NOT NULL, "
                "email VARCHAR(255) NOT NULL UNIQUE, "
                "department VARCHAR(120) NOT NULL, "
                "semester INTEGER NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO students "
                "(student_id, full_name, email, department, semester) "
                "VALUES ('STU-LEGACY-1', 'Legacy Student', "
                "'legacy@example.edu', 'Computer Science', 4)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE attendance_records ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "student_id VARCHAR(32) NOT NULL, "
                "subject VARCHAR(120) NOT NULL, "
                "class_date DATE NOT NULL, "
                "status VARCHAR(10) NOT NULL, "
                "remarks VARCHAR(500))"
            )
        )
        connection.execute(
            text(
                "INSERT INTO attendance_records "
                "(student_id, subject, class_date, status) "
                "VALUES ('STU-LEGACY-1', 'Networks', '2026-10-20', 'present')"
            )
        )
    engine.dispose()

    migration_config = Config(str(BACKEND_DIR / "alembic.ini"))
    migration_config.attributes["database_url"] = database_url
    migration_config.attributes["configure_logger"] = False
    command.upgrade(migration_config, "head")

    migrated_engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )
    with migrated_engine.connect() as connection:
        student = connection.execute(
            text(
                "SELECT student_id, full_name, is_demo FROM students "
                "WHERE student_id = 'STU-LEGACY-1'"
            )
        ).one()
        attendance_count = connection.execute(
            text(
                "SELECT count(*) FROM attendance_records "
                "WHERE student_id = 'STU-LEGACY-1'"
            )
        ).scalar_one()
        new_tables = set(inspect(connection).get_table_names())
    assert student == ("STU-LEGACY-1", "Legacy Student", 1)
    assert attendance_count == 1
    assert {
        "academic_years",
        "departments",
        "branches",
        "semesters",
        "class_sections",
        "faculty_section_assignments",
        "subjects",
        "student_enrollments",
    }.issubset(new_tables)
    migrated_engine.dispose()
