from app.core.config import AUTH_COOKIE_NAME
from app.models.auth import UserAccount
from app.models.student import Student


def test_auth_me_requires_a_valid_session(auth_env):
    client = auth_env["client"]
    client.cookies.delete(AUTH_COOKIE_NAME, path="/api")

    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_login_sets_http_only_session_cookie_and_returns_identity(auth_env):
    client = auth_env["client"]
    client.cookies.delete(AUTH_COOKIE_NAME, path="/api")

    response = client.post(
        "/api/auth/login",
        json={
            "email": "STUDENT@example.edu",
            "password": "Student-Test-Password-12",
        },
    )

    assert response.status_code == 200
    assert response.json()["role"] == "student"
    assert response.json()["display_name"] == "Test Student"
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert client.get("/api/auth/me").json()["id"] == response.json()["id"]


def test_faculty_can_log_in_and_student_endpoints_deny_faculty(auth_env):
    client = auth_env["client"]
    client.cookies.delete(AUTH_COOKIE_NAME, path="/api")

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "faculty@example.edu",
            "password": "Faculty-Test-Password-12",
        },
    )

    assert login_response.status_code == 200
    assert login_response.json()["role"] == "faculty"
    assert login_response.json()["display_name"] == "Test Faculty"
    assert client.get("/api/auth/me").json()["role"] == "faculty"
    assert client.get("/api/students/me").status_code == 403
    assert client.get("/api/dashboard").status_code == 403


def test_login_rejects_invalid_credentials(auth_env):
    client = auth_env["client"]
    client.cookies.delete(AUTH_COOKIE_NAME, path="/api")

    response = client.post(
        "/api/auth/login",
        json={"email": "student@example.edu", "password": "incorrect"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Email or password is incorrect."


def test_logout_revokes_the_session(auth_env):
    client = auth_env["client"]

    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_roles_are_enforced_by_the_backend(auth_env):
    client = auth_env["client"]

    assert client.get("/api/students/me").status_code == 200
    client.cookies.set(
        AUTH_COOKIE_NAME,
        auth_env["faculty_token"],
        path="/api",
    )
    assert client.get("/api/students/me").status_code == 403


def test_disabled_accounts_cannot_log_in(auth_env):
    with auth_env["session_factory"]() as db:
        student = db.get(UserAccount, auth_env["student_user_id"])
        student.is_active = False
        db.commit()

    client = auth_env["client"]
    client.cookies.delete(AUTH_COOKIE_NAME, path="/api")
    response = client.post(
        "/api/auth/login",
        json={
            "email": "student@example.edu",
            "password": "Student-Test-Password-12",
        },
    )

    assert response.status_code == 401


def test_demo_student_profile_cannot_be_used_as_a_private_account(auth_env):
    with auth_env["session_factory"]() as db:
        student = db.get(Student, "STU-TEST-0001")
        student.is_demo = True
        db.commit()

    response = auth_env["client"].get("/api/students/me")

    assert response.status_code == 403


def test_untrusted_origin_is_rejected(auth_env):
    response = auth_env["client"].post(
        "/api/auth/logout",
        headers={"Origin": "https://untrusted.example"},
    )

    assert response.status_code == 403
