from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import AUTH_COOKIE_NAME
from app.core.security import (
    create_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.models.academic_structure import (
    AcademicYear,
    Branch,
    ClassSection,
    Department,
    FacultySectionAssignment,
    Semester,
    StudentEnrollment,
)
from app.models.auth import (
    AuthSession,
    FacultyAccount,
    StudentAccount,
    StudentPasswordSetupToken,
    UserAccount,
)
from app.models.academic import AttendanceRecord
from app.models.student import Student
from app.services import student_account_service
from uuid import uuid4


def create_section(db, faculty_user_id, section_name="A"):
    year = AcademicYear(
        name=f"2098-{section_name}",
        start_date=date(2098, 7, 1),
        end_date=date(2099, 6, 30),
        created_by_user_id=faculty_user_id,
    )
    department = Department(
        code=f"D{section_name}",
        name="Engineering",
        created_by_user_id=faculty_user_id,
    )
    db.add_all([year, department])
    db.flush()
    branch = Branch(
        department_id=department.id,
        code=f"B{section_name}",
        name="Computer Science",
        created_by_user_id=faculty_user_id,
    )
    db.add(branch)
    db.flush()
    semester = Semester(
        academic_year_id=year.id,
        number=1,
        name="Semester 1",
        created_by_user_id=faculty_user_id,
    )
    db.add(semester)
    db.flush()
    section = ClassSection(
        branch_id=branch.id,
        academic_year_id=year.id,
        semester_id=semester.id,
        name=section_name,
        created_by_user_id=faculty_user_id,
    )
    db.add(section)
    db.flush()
    db.add(
        FacultySectionAssignment(
            faculty_user_id=faculty_user_id,
            section_id=section.id,
        )
    )
    return section


def provision(faculty_client, section_id):
    return faculty_client.post(
        "/api/faculty/student-accounts/provision",
        json={"section_id": section_id},
    )


def setup_token_from_response(response):
    return parse_qs(urlparse(response.json()["local_setup_links"][0]["url"]).query)[
        "token"
    ][0]


def allow_local_setup(monkeypatch):
    monkeypatch.setattr(student_account_service.config, "APP_ENV", "development")
    monkeypatch.setattr(
        student_account_service.config,
        "ALLOW_LOCAL_STUDENT_SETUP_LINKS",
        True,
    )
    monkeypatch.setattr(student_account_service.config, "SMTP_HOST", "")
    monkeypatch.setattr(student_account_service.config, "SMTP_FROM_EMAIL", "")
    monkeypatch.setattr(student_account_service.config, "SMTP_USERNAME", "")
    monkeypatch.setattr(student_account_service.config, "SMTP_PASSWORD", "")


def create_provisioning_fixture(auth_env, monkeypatch):
    allow_local_setup(monkeypatch)
    with auth_env["session_factory"]() as db:
        section = create_section(db, auth_env["faculty_user_id"])
        db.add_all(
            [
                Student(
                    student_id="STU-UNLINKED-1",
                    full_name="New Learner",
                    email="new-learner@example.edu",
                    department="Computer Science",
                    semester=1,
                    is_demo=False,
                ),
                Student(
                    student_id="STU-DEMO-1",
                    full_name="Demo Learner",
                    email="demo@example.edu",
                    department="Computer Science",
                    semester=1,
                    is_demo=True,
                ),
                Student(
                    student_id="STU-INVALID-EMAIL",
                    full_name="Invalid Email",
                    email="not-an-email",
                    department="Computer Science",
                    semester=1,
                    is_demo=False,
                ),
                Student(
                    student_id="STU-EMAIL-COLLISION",
                    full_name="Existing Account Email",
                    email="faculty@example.edu",
                    department="Computer Science",
                    semester=1,
                    is_demo=False,
                ),
            ]
        )
        db.flush()
        db.add_all(
            [
                StudentEnrollment(
                    student_id="STU-TEST-0001",
                    section_id=section.id,
                    semester_id=section.semester_id,
                ),
                StudentEnrollment(
                    student_id="STU-TEST-0002",
                    section_id=section.id,
                    semester_id=section.semester_id,
                ),
                StudentEnrollment(
                    student_id="STU-UNLINKED-1",
                    section_id=section.id,
                    semester_id=section.semester_id,
                ),
                StudentEnrollment(
                    student_id="STU-DEMO-1",
                    section_id=section.id,
                    semester_id=section.semester_id,
                ),
                StudentEnrollment(
                    student_id="STU-INVALID-EMAIL",
                    section_id=section.id,
                    semester_id=section.semester_id,
                ),
                StudentEnrollment(
                    student_id="STU-EMAIL-COLLISION",
                    section_id=section.id,
                    semester_id=section.semester_id,
                ),
            ]
        )
        db.commit()
        section_id = section.id
    faculty_client = auth_env["client"]
    faculty_client.cookies.set(
        AUTH_COOKIE_NAME,
        auth_env["faculty_token"],
        path="/api",
    )
    return faculty_client, section_id


def test_bulk_provisioning_creates_one_link_and_reports_existing_or_invalid_students(
    auth_env,
    monkeypatch,
):
    faculty_client, section_id = create_provisioning_fixture(auth_env, monkeypatch)

    response = provision(faculty_client, section_id)

    assert response.status_code == 200
    result = response.json()
    assert result["summary"] == {
        "created": 1,
        "already_linked": 2,
        "skipped": 2,
        "failed": 1,
        "delivery_failed": 0,
    }
    assert result["local_development_only"] is True
    assert [item["student_id"] for item in result["local_setup_links"]] == [
        "STU-UNLINKED-1"
    ]
    token = setup_token_from_response(response)
    with auth_env["session_factory"]() as db:
        link = db.scalar(
            select(StudentAccount).where(
                StudentAccount.student_id == "STU-UNLINKED-1"
            )
        )
        account = db.get(UserAccount, link.user_id)
        token_record = db.scalar(
            select(StudentPasswordSetupToken).where(
                StudentPasswordSetupToken.user_id == link.user_id
            )
        )
        assert account.role == "student"
        assert account.password_setup_required is True
        assert account.password_hash != token
        assert token_record.token_hash != token
        assert token_record.token_hash == student_account_service.hash_session_token(token)
        assert db.scalar(
            select(func.count()).select_from(StudentAccount).where(
                StudentAccount.student_id == "STU-UNLINKED-1"
            )
        ) == 1


def test_setup_token_expires_is_single_use_and_enables_student_id_and_email_login(
    auth_env,
    monkeypatch,
):
    faculty_client, section_id = create_provisioning_fixture(auth_env, monkeypatch)
    with auth_env["session_factory"]() as db:
        db.add(
            AttendanceRecord(
                student_id="STU-TEST-0001",
                subject="Private subject",
                class_date=date(2026, 10, 20),
                status="present",
            )
        )
        db.commit()
    provisioned = provision(faculty_client, section_id)
    token = setup_token_from_response(provisioned)

    with auth_env["session_factory"]() as db:
        token_record = db.scalar(
            select(StudentPasswordSetupToken).where(
                StudentPasswordSetupToken.token_hash
                == student_account_service.hash_session_token(token)
            )
        )
        token_record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    expired = auth_env["client"].post(
        "/api/auth/student/setup",
        json={"token": token, "password": "Correct-Horse-Battery-12"},
    )
    assert expired.status_code == 400
    assert "expired" in expired.json()["detail"]

    refreshed = provision(faculty_client, section_id)
    assert refreshed.json()["summary"]["already_linked"] == 3
    active_token = setup_token_from_response(refreshed)
    password = "Correct-Horse-Battery-12"
    completed = auth_env["client"].post(
        "/api/auth/student/setup",
        json={"token": active_token, "password": password},
    )
    assert completed.status_code == 204
    reused = auth_env["client"].post(
        "/api/auth/student/setup",
        json={"token": active_token, "password": "Another-Valid-Password-12"},
    )
    assert reused.status_code == 400

    with auth_env["session_factory"]() as db:
        account_link = db.scalar(
            select(StudentAccount).where(
                StudentAccount.student_id == "STU-UNLINKED-1"
            )
        )
        account = db.get(UserAccount, account_link.user_id)
        token_record = db.scalar(
            select(StudentPasswordSetupToken).where(
                StudentPasswordSetupToken.user_id == account.id
            )
        )
        assert account.password_setup_required is False
        assert verify_password(password, account.password_hash)
        assert token_record.used_at is not None

    client = auth_env["client"]
    for identifier in ("STU-UNLINKED-1", "new-learner@example.edu"):
        client.cookies.delete(AUTH_COOKIE_NAME, path="/api")
        login_response = client.post(
            "/api/auth/login",
            json={"email": identifier, "password": password},
        )
        assert login_response.status_code == 200
        assert login_response.json()["role"] == "student"
        assert client.get("/api/students/me").json()["student_id"] == "STU-UNLINKED-1"
        assert client.get("/api/attendance").json() == []
        assert client.get("/api/dashboard").json()["attendance"]["total_classes"] == 0


def test_local_setup_links_are_unavailable_outside_development(
    auth_env,
    monkeypatch,
):
    faculty_client, section_id = create_provisioning_fixture(auth_env, monkeypatch)
    monkeypatch.setattr(student_account_service.config, "APP_ENV", "production")

    response = provision(faculty_client, section_id)

    assert response.status_code == 503
    with auth_env["session_factory"]() as db:
        assert db.scalar(
            select(StudentAccount).where(
                StudentAccount.student_id == "STU-UNLINKED-1"
            )
        ) is None


def test_bulk_provisioning_is_idempotent_and_does_not_duplicate_links(
    auth_env,
    monkeypatch,
):
    faculty_client, section_id = create_provisioning_fixture(auth_env, monkeypatch)
    assert provision(faculty_client, section_id).status_code == 200

    second = provision(faculty_client, section_id)

    assert second.status_code == 200
    assert second.json()["summary"] == {
        "created": 0,
        "already_linked": 3,
        "skipped": 2,
        "failed": 1,
        "delivery_failed": 0,
    }
    with auth_env["session_factory"]() as db:
        assert db.scalar(
            select(func.count()).select_from(StudentAccount).where(
                StudentAccount.student_id == "STU-UNLINKED-1"
            )
        ) == 1


def test_account_email_uniqueness_is_case_insensitive(auth_env):
    with auth_env["session_factory"]() as db:
        db.add(
            UserAccount(
                id=str(uuid4()),
                email="FACULTY@example.edu",
                password_hash=hash_password("Unique-Test-Password-12"),
                role="student",
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        else:
            raise AssertionError("Case-insensitive duplicate account email was accepted.")


def test_faculty_cannot_provision_accounts_outside_assigned_sections(
    auth_env,
    monkeypatch,
):
    allow_local_setup(monkeypatch)
    other_faculty_id = str(uuid4())
    other_faculty_token = create_session_token()
    with auth_env["session_factory"]() as db:
        other_faculty = UserAccount(
            id=other_faculty_id,
            email="other-faculty@example.edu",
            password_hash=hash_password("Other-Faculty-Password-12"),
            role="faculty",
        )
        other_faculty.faculty_account = FacultyAccount(
            faculty_code="FAC-OTHER-PROVISION",
            full_name="Other Faculty",
        )
        other_section = create_section(db, other_faculty_id, "B")
        other_faculty.sessions.append(
            AuthSession(
                id=str(uuid4()),
                token_hash=hash_session_token(other_faculty_token),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        db.add(other_faculty)
        db.commit()
        section_id = other_section.id
    client = auth_env["client"]
    client.cookies.set(AUTH_COOKIE_NAME, auth_env["faculty_token"], path="/api")

    response = provision(client, section_id)

    assert response.status_code == 404
    student_client = auth_env["client"]
    student_client.cookies.set(
        AUTH_COOKIE_NAME,
        auth_env["student_token"],
        path="/api",
    )
    assert provision(student_client, section_id).status_code == 403


def test_email_delivery_sends_links_but_never_returns_setup_tokens(
    auth_env,
    monkeypatch,
):
    faculty_client, section_id = create_provisioning_fixture(auth_env, monkeypatch)
    sent = []
    monkeypatch.setattr(student_account_service.config, "ALLOW_LOCAL_STUDENT_SETUP_LINKS", False)
    monkeypatch.setattr(student_account_service.config, "SMTP_HOST", "smtp.example.edu")
    monkeypatch.setattr(
        student_account_service.config,
        "SMTP_FROM_EMAIL",
        "noreply@example.edu",
    )
    monkeypatch.setattr(
        student_account_service,
        "_send_setup_email",
        lambda email, name, url: sent.append((email, name, url)),
    )

    response = provision(faculty_client, section_id)

    assert response.status_code == 200
    result = response.json()
    assert result["delivery_mode"] == "email"
    assert result["summary"]["created"] == 1
    assert result["summary"]["delivery_failed"] == 0
    assert sent[0][0] == "new-learner@example.edu"
    assert "token=" in sent[0][2]
    assert "local_setup_links" not in result
    assert "token" not in response.text
