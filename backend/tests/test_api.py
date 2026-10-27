def test_health_check(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_frontend_origin_is_allowed_by_cors(client):
    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_student_profile_is_the_authenticated_student(client):
    response = client.get("/api/students/me")

    assert response.status_code == 200
    assert response.json() == {
        "student_id": "STU-TEST-0001",
        "full_name": "Test Student",
        "email": "student@example.edu",
        "department": "Computer Science",
        "semester": 1,
    }


def test_dashboard_data_matches_academic_endpoints(client):
    dashboard_response = client.get("/api/dashboard")
    attendance_response = client.get("/api/attendance/summary")
    marks_response = client.get("/api/marks")

    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    attendance_summary = attendance_response.json()
    marks = marks_response.json()
    assert dashboard["attendance"]["percentage"] is None
    assert attendance_summary["percentage"] == 0.0
    assert dashboard["attendance"]["classes_attended"] == 0
    assert dashboard["attendance"]["total_classes"] == attendance_summary["total_classes"] == 0
    assert dashboard["average_marks"]["percentage"] is None
    assert marks == []
    assert dashboard["pending_assignments"] == 0
    assert dashboard["recent_activity"] == []
    assert dashboard["upcoming_deadlines"] == []
