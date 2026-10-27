import ipaddress
import os
from contextlib import ExitStack, asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlalchemy.pool import StaticPool

from app.core.config import AUTH_COOKIE_NAME
from app.core.security import create_session_token, hash_session_token, hash_password
from app.database import Base, DATABASE_URL, get_db
from app.main import app
from app.models import Student
from app.models.auth import AuthSession, FacultyAccount, StudentAccount, UserAccount


@pytest.fixture
def auth_env(monkeypatch, request):
    test_url_value = os.environ.get("EDUPILOT_TEST_DATABASE_URL")
    schema_name = None
    schema_created = False

    if test_url_value is None:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        test_engine = engine
    else:
        try:
            test_url = make_url(test_url_value)
            app_url = make_url(DATABASE_URL)
        except (ArgumentError, TypeError, ValueError):
            pytest.fail("Invalid PostgreSQL test database configuration.")

        test_target = (
            (test_url.host or "").lower(),
            test_url.port or 5432,
            test_url.database,
            test_url.username,
        )
        app_target = (
            (app_url.host or "").lower(),
            app_url.port or 5432,
            app_url.database,
            app_url.username,
        )
        if (
            test_url.drivername != "postgresql+psycopg"
            or (test_url.host or "").lower()
            not in {"localhost", "127.0.0.1", "::1"}
            or test_url.database != "edupilot_test"
            or test_url.username != "edupilot_test"
            or bool(test_url.query)
            or test_target == app_target
        ):
            pytest.fail("PostgreSQL tests require the dedicated local test database.")

        engine = create_engine(
            test_url,
            pool_pre_ping=True,
            hide_parameters=True,
        )

        def cleanup_postgres():
            try:
                if schema_created:
                    with engine.begin() as connection:
                        connection.execute(
                            DropSchema(schema_name, cascade=True, if_exists=True)
                        )
            finally:
                engine.dispose()

        request.addfinalizer(cleanup_postgres)

        schema_name = f"edupilot_api_test_{uuid4().hex}"
        with engine.connect() as connection:
            database, username, server_address, server_port = connection.execute(
                text(
                    "SELECT current_database(), current_user, "
                    "inet_server_addr()::text, current_setting('port')"
                )
            ).one()
            schema_exists = connection.execute(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM pg_catalog.pg_namespace "
                    "WHERE nspname = :schema_name"
                    ")"
                ),
                {"schema_name": schema_name},
            ).scalar_one()

        try:
            server_is_loopback = (
                server_address is not None
                and ipaddress.ip_address(server_address).is_loopback
            )
        except ValueError:
            server_is_loopback = False

        if (
            database != "edupilot_test"
            or username != "edupilot_test"
            or not server_is_loopback
            or server_port != str(test_url.port or 5432)
            or schema_exists
        ):
            pytest.fail("PostgreSQL test target is not the approved local test server.")

        with engine.begin() as connection:
            connection.execute(CreateSchema(schema_name))
            schema_created = True

        test_engine = engine.execution_options(
            schema_translate_map={None: schema_name}
        )

        @asynccontextmanager
        async def test_lifespan(_app):
            yield

        monkeypatch.setattr(app.router, "lifespan_context", test_lifespan)

    if test_url_value is None:
        request.addfinalizer(engine.dispose)

    Base.metadata.create_all(bind=test_engine)
    testing_session_local = sessionmaker(bind=test_engine, autoflush=False)
    student_user_id = str(uuid4())
    other_student_user_id = str(uuid4())
    faculty_user_id = str(uuid4())
    student_token = create_session_token()
    other_student_token = create_session_token()
    faculty_token = create_session_token()

    with testing_session_local() as db:
        db.add(
            Student(
                student_id="STU-TEST-0001",
                full_name="Test Student",
                email="student@example.edu",
                department="Computer Science",
                semester=1,
                is_demo=False,
            )
        )
        db.add(
            Student(
                student_id="STU-TEST-0002",
                full_name="Other Test Student",
                email="other-student@example.edu",
                department="Physics",
                semester=2,
                is_demo=False,
            )
        )
        student = UserAccount(
            id=student_user_id,
            email="student@example.edu",
            password_hash=hash_password("Student-Test-Password-12"),
            role="student",
        )
        student.student_account = StudentAccount(student_id="STU-TEST-0001")
        other_student = UserAccount(
            id=other_student_user_id,
            email="other-student@example.edu",
            password_hash=hash_password("Other-Student-Password-12"),
            role="student",
        )
        other_student.student_account = StudentAccount(student_id="STU-TEST-0002")
        faculty = UserAccount(
            id=faculty_user_id,
            email="faculty@example.edu",
            password_hash=hash_password("Faculty-Test-Password-12"),
            role="faculty",
        )
        faculty.faculty_account = FacultyAccount(
            faculty_code="FAC-TEST-1",
            full_name="Test Faculty",
        )
        db.add_all([student, other_student, faculty])
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        db.add_all(
            [
                AuthSession(
                    id=str(uuid4()),
                    user_id=student_user_id,
                    token_hash=hash_session_token(student_token),
                    expires_at=expires_at,
                ),
                AuthSession(
                    id=str(uuid4()),
                    user_id=faculty_user_id,
                    token_hash=hash_session_token(faculty_token),
                    expires_at=expires_at,
                ),
                AuthSession(
                    id=str(uuid4()),
                    user_id=other_student_user_id,
                    token_hash=hash_session_token(other_student_token),
                    expires_at=expires_at,
                ),
            ]
        )
        db.commit()

    def override_get_db():
        with testing_session_local() as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db, override_get_db)
    with ExitStack() as stack:
        client = stack.enter_context(TestClient(app))
        client.cookies.set(AUTH_COOKIE_NAME, student_token, path="/api")
        yield {
            "client": client,
            "student_token": student_token,
            "other_student_token": other_student_token,
            "faculty_token": faculty_token,
            "student_user_id": student_user_id,
            "other_student_user_id": other_student_user_id,
            "faculty_user_id": faculty_user_id,
            "session_factory": testing_session_local,
        }


@pytest.fixture
def client(auth_env):
    return auth_env["client"]
