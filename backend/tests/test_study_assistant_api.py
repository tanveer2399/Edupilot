import json
from datetime import date, time, timedelta
from uuid import uuid4
from urllib.error import HTTPError

import pytest

from app.core import config
from app.core.config import AUTH_COOKIE_NAME
from app.models.academic import Assignment, AttendanceRecord, MarkRecord, TimetableEntry
from app.models.academic_structure import (
    AcademicYear,
    Branch,
    ClassSection,
    Department,
    Semester,
    StudentEnrollment,
    Subject,
)
from app.models.auth import FacultyAccount, UserAccount
from app.core.security import hash_password
from app.models.student import Student
from app.services import study_assistant_service
from app.services.student_academic_context_service import (
    build_student_academic_context,
)
from app.services.study_assistant_service import StudyAssistantError


def seed_complete_academic_context(auth_env):
    today = date.today()
    with auth_env["session_factory"]() as db:
        faculty_id = str(uuid4())
        faculty = UserAccount(
            id=faculty_id,
            email="context-faculty@example.edu",
            password_hash=hash_password("Context-Faculty-Password-12"),
            role="faculty",
        )
        faculty.faculty_account = FacultyAccount(
            faculty_code=f"FAC-{faculty_id[:8]}",
            full_name="Context Faculty",
        )
        db.add(faculty)
        db.flush()
        year = AcademicYear(
            name=f"CTX-{faculty_id[:6]}",
            start_date=today - timedelta(days=180),
            end_date=today + timedelta(days=180),
            created_by_user_id=faculty_id,
        )
        department = Department(
            code=f"CTX{faculty_id[:4]}",
            name="Computing",
            created_by_user_id=faculty_id,
        )
        db.add_all([year, department])
        db.flush()
        branch = Branch(
            department_id=department.id,
            code=f"BR{faculty_id[:4]}",
            name="Computer Science",
            created_by_user_id=faculty_id,
        )
        db.add(branch)
        db.flush()
        semester = Semester(
            academic_year_id=year.id,
            number=1,
            name="Semester 1",
            created_by_user_id=faculty_id,
        )
        db.add(semester)
        db.flush()
        section = ClassSection(
            branch_id=branch.id,
            academic_year_id=year.id,
            semester_id=semester.id,
            name="CTX",
            created_by_user_id=faculty_id,
        )
        db.add(section)
        db.flush()
        db.add(
            StudentEnrollment(
                student_id="STU-TEST-0001",
                section_id=section.id,
                semester_id=semester.id,
            )
        )
        db.add_all(
            [
                Subject(
                    branch_id=branch.id,
                    semester_id=semester.id,
                    code="MATH101",
                    name="Mathematics",
                    credits=3,
                    created_by_user_id=faculty_id,
                ),
                Subject(
                    branch_id=branch.id,
                    semester_id=semester.id,
                    code="PHY101",
                    name="Physics",
                    credits=4,
                    created_by_user_id=faculty_id,
                ),
                AttendanceRecord(
                    student_id="STU-TEST-0001",
                    subject="Mathematics",
                    class_date=today - timedelta(days=3),
                    status="present",
                ),
                AttendanceRecord(
                    student_id="STU-TEST-0001",
                    subject="Mathematics",
                    class_date=today - timedelta(days=2),
                    status="absent",
                ),
                AttendanceRecord(
                    student_id="STU-TEST-0001",
                    subject="Physics",
                    class_date=today - timedelta(days=1),
                    status="late",
                ),
                AttendanceRecord(
                    student_id="STU-TEST-0002",
                    subject="Secret Subject",
                    class_date=today,
                    status="present",
                ),
                MarkRecord(
                    student_id="STU-TEST-0001",
                    subject="Mathematics",
                    assessment_name="Quiz 1",
                    marks_obtained=8,
                    maximum_marks=10,
                    assessment_date=today - timedelta(days=7),
                ),
                MarkRecord(
                    student_id="STU-TEST-0001",
                    subject="Mathematics",
                    assessment_name="Midterm",
                    marks_obtained=12,
                    maximum_marks=20,
                    assessment_date=today - timedelta(days=2),
                ),
                MarkRecord(
                    student_id="STU-TEST-0002",
                    subject="Secret Subject",
                    assessment_name="Secret Exam",
                    marks_obtained=100,
                    maximum_marks=100,
                    assessment_date=today,
                ),
                Assignment(
                    student_id="STU-TEST-0001",
                    subject="Mathematics",
                    title="Upcoming problem set",
                    due_date=today + timedelta(days=3),
                    status="pending",
                ),
                Assignment(
                    student_id="STU-TEST-0001",
                    subject="Physics",
                    title="Submitted lab report",
                    due_date=today - timedelta(days=2),
                    status="submitted",
                ),
                TimetableEntry(
                    student_id="STU-TEST-0001",
                    subject="Mathematics",
                    day_of_week=today.strftime("%A"),
                    start_time=time(10, 0),
                    end_time=time(11, 0),
                    location="Room 101",
                ),
                Assignment(
                    student_id="STU-TEST-0002",
                    subject="Secret Subject",
                    title="Secret Assignment",
                    due_date=today + timedelta(days=2),
                    status="pending",
                ),
                TimetableEntry(
                    student_id="STU-TEST-0002",
                    subject="Secret Subject",
                    day_of_week=today.strftime("%A"),
                    start_time=time(12, 0),
                    end_time=time(13, 0),
                    location="Secret Room",
                ),
            ]
        )
        db.commit()


def test_ollama_request_uses_the_requested_temperature(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"message":{"content":"response"},"done_reason":"stop"}'

    def fake_urlopen(request, timeout):
        assert timeout > 0
        assert json.loads(request.data)["options"]["temperature"] == 0.7
        return FakeResponse()

    monkeypatch.setattr(study_assistant_service, "urlopen", fake_urlopen)
    response = study_assistant_service._call_ollama(
        [{"role": "user", "content": "Generate a quiz."}],
        response_format={"type": "object"},
        temperature=0.7,
    )

    assert response.content == "response"

def test_chat_returns_answer_and_conversation_id(client, monkeypatch):
    async def fake_request(messages):
        assert messages[0]["role"] == "system"
        assert messages[-1] == {
            "role": "user",
            "content": "Explain indexing simply.",
        }
        return "An index is like a book's lookup list."

    monkeypatch.setattr(study_assistant_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/study-assistant/chat",
        json={"message": "Explain indexing simply."},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "An index is like a book's lookup list."
    assert response.json()["conversation_id"]


def test_assistant_uses_authenticated_students_attendance_marks_and_assignments(
    client,
    auth_env,
    monkeypatch,
):
    seed_complete_academic_context(auth_env)
    captured = []

    async def fake_request(messages):
        captured.extend(messages)
        return "Your recorded overall attendance is 66.67%."

    monkeypatch.setattr(study_assistant_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/study-assistant/chat",
        json={"message": "Summarize my complete academic profile."},
    )

    assert response.status_code == 200
    context_message = captured[1]
    assert context_message["role"] == "system"
    assert "Trusted academic context" in context_message["content"]
    assert '"overall_percentage":66.67' in context_message["content"]
    assert '"classes_held":2' in context_message["content"]
    assert '"absences":1' in context_message["content"]
    assert '"percentage":50.0' in context_message["content"]
    assert '"overall_percentage":66.67' in context_message["content"]
    assert '"assessment_name":"Midterm"' in context_message["content"]
    assert '"pending":1' in context_message["content"]
    assert "Upcoming problem set" in context_message["content"]
    assert '"weekly_schedule":' in context_message["content"]
    assert '"room":"Room 101"' in context_message["content"]
    assert "Computing" in context_message["content"]
    assert "Secret Subject" not in context_message["content"]
    assert "Secret Exam" not in context_message["content"]
    assert "Secret Assignment" not in context_message["content"]
    assert "Secret Room" not in context_message["content"]
    assert "STU-TEST-0002" not in context_message["content"]


def test_subject_performance_comparison_uses_weighted_authenticated_marks(
    client,
    auth_env,
    monkeypatch,
):
    seed_complete_academic_context(auth_env)
    with auth_env["session_factory"]() as db:
        db.add(
            MarkRecord(
                student_id="STU-TEST-0001",
                subject="Physics",
                assessment_name="Lab assessment",
                marks_obtained=18,
                maximum_marks=20,
                assessment_date=date.today(),
            )
        )
        db.commit()

    captured = []

    async def fake_request(messages):
        captured.extend(messages)
        return (
            "Mathematics: 20/30 = 66.67%; Physics: 18/20 = 90%. "
            "Physics leads by 23.33 percentage points."
        )

    monkeypatch.setattr(study_assistant_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/study-assistant/chat",
        json={"message": "How am I performing in Mathematics compared with Physics?"},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == (
        "Mathematics: 20/30 = 66.67%; Physics: 18/20 = 90%. "
        "Physics leads by 23.33 percentage points."
    )
    assert len(captured) == 3
    assert "calculate weighted percentages across assessments" in captured[0]["content"]
    context_message = captured[1]["content"]
    assert "Trusted academic context" in context_message
    context = json.loads(context_message.split("\n", maxsplit=1)[1])
    math = next(
        subject
        for subject in context["marks"]["subject_wise"]
        if subject["subject"] == "Mathematics"
    )
    physics = next(
        subject
        for subject in context["marks"]["subject_wise"]
        if subject["subject"] == "Physics"
    )
    assert (math["marks_earned"], math["marks_possible"], math["percentage"]) == (
        20.0,
        30.0,
        66.67,
    )
    assert (physics["marks_earned"], physics["marks_possible"], physics["percentage"]) == (
        18.0,
        20.0,
        90.0,
    )
    assessments = context["marks"]["recent_assessments"]
    assert {
        (item["subject"], item["assessment_name"], item["marks_earned"], item["marks_possible"])
        for item in assessments
    } == {
        ("Mathematics", "Quiz 1", 8, 10),
        ("Mathematics", "Midterm", 12, 20),
        ("Physics", "Lab assessment", 18, 20),
    }
    assert "Secret Subject" not in context_message
    assert "Secret Exam" not in context_message
    assert "STU-TEST-0002" not in context_message


@pytest.mark.parametrize(
    "question",
    [
        "Which Mathematics topics should I focus on to improve my marks?",
        "What should I work on in Mathematics to raise my score?",
        "Based on my Physics grades, what concepts should I review?",
    ],
)
def test_subject_improvement_questions_use_only_authenticated_marks_context(
    question,
    client,
    auth_env,
    monkeypatch,
):
    seed_complete_academic_context(auth_env)
    captured = []

    async def fake_request(messages):
        captured.extend(messages)
        if "Physics" in question:
            return (
                "No Physics assessment scores are recorded for you. Topic-level "
                "results are unavailable; after assessments are recorded, review "
                "incorrect answers, identify weak concepts, and practice similar "
                "questions."
            )
        return (
            "Your Mathematics assessments total 20/30 (66.67%). The database does "
            "not contain topic-level marks or question-level mistakes, so specific "
            "weak topics cannot yet be identified. Review incorrect answers from "
            "the Mathematics Quiz 1 and Midterm, identify the concepts involved, "
            "and practice similar questions."
        )

    monkeypatch.setattr(study_assistant_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/study-assistant/chat",
        json={"message": question},
    )

    assert response.status_code == 200
    if "Physics" in question:
        assert "No Physics assessment scores are recorded" in response.json()["answer"]
        assert "Mathematics" not in response.json()["answer"]
    else:
        assert "20/30 (66.67%)" in response.json()["answer"]
        assert (
            "The database does not contain topic-level marks or question-level mistakes"
            in response.json()["answer"]
        )
        assert "specific weak topics cannot yet be identified" in response.json()["answer"]
        assert (
            "Review incorrect answers from the Mathematics Quiz 1 and Midterm"
            in response.json()["answer"]
        )
        assert "Physics" not in response.json()["answer"]
    assert len(captured) == 3
    assert (
        "do not cite other subjects or an all-subject aggregate unless the student"
        in captured[0]["content"].replace("\n", " ")
    )
    assert (
        "specific weak topics cannot yet be identified"
        in captured[0]["content"].replace("\n", " ")
    )
    assert "Trusted academic context" in captured[1]["content"]
    context = json.loads(captured[1]["content"].split("\n", maxsplit=1)[1])
    assert set(context) == {"data_freshness", "marks"}
    assert context["marks"]["overall_percentage"] == 66.67
    assert context["marks"]["topic_level_results"] == {
        "status": "unavailable",
        "reason": (
            "Records contain subject-level assessment totals, not "
            "question-level answers or topic-level results."
        ),
    }
    assert {
        (
            item["assessment_name"],
            item["marks_earned"],
            item["marks_possible"],
        )
        for item in context["marks"]["recent_assessments"]
        if item["subject"] == "Mathematics"
    } == {("Quiz 1", 8, 10), ("Midterm", 12, 20)}
    assert "Secret Subject" not in captured[1]["content"]
    assert "Secret Exam" not in captured[1]["content"]
    assert "STU-TEST-0002" not in captured[1]["content"]


def test_attendance_question_loads_only_attendance_context(client, auth_env, monkeypatch):
    seed_complete_academic_context(auth_env)
    captured = []

    async def fake_request(messages):
        captured.extend(messages)
        return "Mathematics: 50%; Physics: 100%."

    monkeypatch.setattr(study_assistant_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/study-assistant/chat",
        json={"message": "Show my attendance for every subject."},
    )

    assert response.status_code == 200
    context = captured[1]["content"]
    assert '"attendance":' in context
    assert '"marks":' not in context
    assert '"assignments":' not in context
    assert "Mathematics" in context
    assert "Physics" in context


@pytest.mark.parametrize(
    "question",
    [
        "What is my attendance percentage?",
        "What is my attendance rate?",
        "What percentage of my classes did I attend?",
        "How many classes have I attended?",
        "How many classes did I miss?",
        "How many absences do I have?",
        "How often was I absent?",
        "Show my attendance records.",
        "Can you show my attendance history?",
        "Do I have an attendance shortage?",
        "Am I meeting the attendance requirement?",
        "How many classes were held for me?",
    ],
)
def test_attendance_questions_use_authenticated_attendance_records(
    question,
    client,
    auth_env,
    monkeypatch,
):
    seed_complete_academic_context(auth_env)
    captured = []

    async def fake_request(messages):
        captured.extend(messages)
        return "Your attendance is 66.67% (2 of 3 recorded classes)."

    monkeypatch.setattr(study_assistant_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/study-assistant/chat",
        json={"message": question},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == (
        "Your attendance is 66.67% (2 of 3 recorded classes)."
    )
    assert len(captured) == 3
    system_prompt = " ".join(captured[0]["content"].split())
    assert "authenticated student's supplied attendance context" in system_prompt
    assert "Present and late count as attended" in system_prompt
    context_message = captured[1]["content"]
    context = json.loads(context_message.split("\n", maxsplit=1)[1])
    assert set(context) == {"data_freshness", "attendance"}
    attendance = context["attendance"]
    assert attendance["status"] == "available"
    assert attendance["classes_attended"] == 2
    assert attendance["classes_held"] == 3
    assert attendance["overall_percentage"] == 66.67
    assert "Secret Subject" not in context_message
    assert "STU-TEST-0002" not in context_message


def test_attendance_context_builder_aggregates_only_exact_student_records(
    auth_env,
):
    seed_complete_academic_context(auth_env)

    with auth_env["session_factory"]() as db:
        student = db.get(Student, "STU-TEST-0001")
        context = build_student_academic_context(db, student, {"attendance"})

    attendance = context["attendance"]
    assert attendance["status"] == "available"
    assert attendance["classes_attended"] == 2
    assert attendance["classes_held"] == 3
    assert attendance["absences"] == 1
    assert attendance["overall_percentage"] == 66.67
    assert {record["subject"] for record in attendance["recent_history"]} == {
        "Mathematics",
        "Physics",
    }
    assert "Secret Subject" not in json.dumps(attendance)


def test_academic_follow_up_retrieves_fresh_context(client, auth_env, monkeypatch):
    seed_complete_academic_context(auth_env)
    calls = []

    async def fake_request(messages):
        calls.append(messages)
        return f"Answer {len(calls)}"

    monkeypatch.setattr(study_assistant_service, "_request_ollama", fake_request)
    first = client.post(
        "/api/study-assistant/chat",
        json={"message": "What is my attendance in Mathematics?"},
    )
    with auth_env["session_factory"]() as db:
        db.add(
            AttendanceRecord(
                student_id="STU-TEST-0001",
                subject="Mathematics",
                class_date=date.today(),
                status="present",
            )
        )
        db.commit()
    followup = client.post(
        "/api/study-assistant/chat",
        json={
            "message": "What about Maths?",
            "conversation_id": first.json()["conversation_id"],
        },
    )

    assert followup.status_code == 200
    assert len(calls[1]) == 5
    assert '"classes_held":3' in calls[1][1]["content"]
    assert '"overall_percentage":75.0' in calls[1][1]["content"]


@pytest.mark.parametrize(
    "question",
    [
        "Explain database indexing in simple words.",
        "What are effective ways to study Mathematics?",
    ],
)
def test_general_study_question_does_not_include_academic_context(
    question,
    client,
    auth_env,
    monkeypatch,
):
    seed_complete_academic_context(auth_env)
    captured = []

    async def fake_request(messages):
        captured.extend(messages)
        return "A database index speeds up lookups."

    monkeypatch.setattr(study_assistant_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/study-assistant/chat",
        json={"message": question},
    )

    assert response.status_code == 200
    assert len(captured) == 2
    assert all("Trusted academic context" not in item["content"] for item in captured)


@pytest.mark.parametrize(
    "question",
    [
        "What is a good attendance percentage for students?",
        "Explain how attendance percentage is calculated.",
        "How does attendance tracking work?",
    ],
)
def test_general_attendance_explanation_does_not_load_personal_context(
    question,
    client,
    auth_env,
    monkeypatch,
):
    seed_complete_academic_context(auth_env)
    captured = []

    async def fake_request(messages):
        captured.extend(messages)
        return "Attendance percentage is based on recorded class sessions."

    monkeypatch.setattr(study_assistant_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/study-assistant/chat",
        json={"message": question},
    )

    assert response.status_code == 200
    assert len(captured) == 2
    assert all("Trusted academic context" not in item["content"] for item in captured)


def test_missing_academic_records_are_marked_unavailable_not_zero(
    client,
    monkeypatch,
):
    captured = []

    async def fake_request(messages):
        captured.extend(messages)
        return "No attendance has been recorded yet."

    monkeypatch.setattr(study_assistant_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/study-assistant/chat",
        json={"message": "What is my overall attendance?"},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "No attendance has been recorded yet."
    assert '"status":"no_records"' in captured[1]["content"]
    assert '"overall_percentage":null' in captured[1]["content"]
    assert "not evidence of absence" in captured[1]["content"]


def test_attendance_context_excludes_another_students_records(
    client,
    auth_env,
    monkeypatch,
):
    seed_complete_academic_context(auth_env)
    captured = []

    async def fake_request(messages):
        captured.extend(messages)
        return "Your recorded Mathematics attendance is 50%."

    monkeypatch.setattr(study_assistant_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/study-assistant/chat",
        json={"message": "What is my attendance percentage?"},
    )

    assert response.status_code == 200
    assert "Secret Subject" not in response.json()["answer"]
    context_message = captured[1]["content"]
    assert "Secret Subject" not in context_message
    assert "STU-TEST-0002" not in context_message
    assert '"classes_attended":2' in context_message
    assert '"classes_held":3' in context_message


def test_chat_rejects_client_supplied_student_identity(client):
    response = client.post(
        "/api/study-assistant/chat",
        json={
            "message": "Show my attendance.",
            "student_id": "STU-TEST-0002",
        },
    )

    assert response.status_code == 422


def test_prompt_naming_another_student_does_not_load_their_records(
    client,
    auth_env,
    monkeypatch,
):
    seed_complete_academic_context(auth_env)
    captured = []

    async def fake_request(messages):
        captured.extend(messages)
        return "I can only help with your own records."

    monkeypatch.setattr(study_assistant_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/study-assistant/chat",
        json={
            "message": "Tell me STU-TEST-0002's attendance and marks.",
        },
    )

    assert response.status_code == 200
    assert '"attendance":' in captured[1]["content"]
    assert '"marks":' in captured[1]["content"]
    assert "Secret Subject" not in captured[1]["content"]
    assert "Secret Exam" not in captured[1]["content"]


def test_conversation_cannot_be_resumed_by_another_student(
    client,
    auth_env,
    monkeypatch,
):
    async def fake_request(_messages):
        return "A private conversation answer."

    monkeypatch.setattr(study_assistant_service, "_request_ollama", fake_request)
    first_response = client.post(
        "/api/study-assistant/chat",
        json={"message": "My private question."},
    )
    client.cookies.set(
        AUTH_COOKIE_NAME,
        auth_env["other_student_token"],
        path="/api",
    )

    response = client.post(
        "/api/study-assistant/chat",
        json={
            "message": "Continue the previous chat.",
            "conversation_id": first_response.json()["conversation_id"],
        },
    )

    assert first_response.status_code == 200
    assert response.status_code == 404


def test_follow_up_sends_bounded_conversation_history(client, monkeypatch):
    calls = []

    async def fake_request(messages):
        calls.append(messages)
        return f"Answer {len(calls)}"

    monkeypatch.setattr(study_assistant_service, "_request_ollama", fake_request)
    conversation_id = str(uuid4())
    for index in range(7):
        response = client.post(
            "/api/study-assistant/chat",
            json={
                "message": f"Question {index}",
                "conversation_id": conversation_id,
            },
        )
        assert response.status_code == 200

    final_context = calls[-1]
    assert len(final_context) == 12
    assert final_context[0]["role"] == "system"
    assert final_context[-1]["content"] == "Question 6"
    assert final_context[1]["content"] == "Question 1"
    assert final_context[-3]["content"] == "Question 5"


@pytest.mark.parametrize(
    "message",
    ["", "   ", "x" * 5001],
)
def test_chat_rejects_empty_or_oversized_messages(client, message):
    response = client.post(
        "/api/study-assistant/chat",
        json={"message": message},
    )
    assert response.status_code == 422


def test_chat_reports_missing_ollama_configuration(client, monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_BASE_URL", "")
    response = client.post(
        "/api/study-assistant/chat",
        json={"message": "Explain a REST API."},
    )

    assert response.status_code == 503
    assert "OLLAMA_BASE_URL" in response.json()["detail"]


def test_chat_reports_missing_model(client, monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_MODEL", "")
    response = client.post(
        "/api/study-assistant/chat",
        json={"message": "Explain normalization."},
    )

    assert response.status_code == 503
    assert "OLLAMA_MODEL" in response.json()["detail"]


def test_chat_rejects_invalid_ollama_url(client, monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_BASE_URL", "not-a-url")
    response = client.post(
        "/api/study-assistant/chat",
        json={"message": "Explain normalization."},
    )

    assert response.status_code == 503
    assert "valid HTTP or HTTPS URL" in response.json()["detail"]


def test_chat_hides_provider_errors_from_internal_trace(client, monkeypatch):
    async def failed_request(_messages):
        raise StudyAssistantError(503, "Could not reach Ollama.")

    monkeypatch.setattr(study_assistant_service, "_request_ollama", failed_request)
    response = client.post(
        "/api/study-assistant/chat",
        json={"message": "Explain recursion."},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Could not reach Ollama."}
    assert "Traceback" not in response.text


def test_chat_reports_ollama_timeout(client, monkeypatch):
    def timed_out(_request, timeout):
        raise TimeoutError("private timeout details")

    monkeypatch.setattr(study_assistant_service, "urlopen", timed_out)
    response = client.post(
        "/api/study-assistant/chat",
        json={"message": "Explain recursion."},
    )

    assert response.status_code == 504
    assert response.json() == {
        "detail": "Ollama took too long to respond. Please try again."
    }
    assert "private timeout details" not in response.text


def test_chat_explains_when_ollama_model_is_not_installed(client, monkeypatch):
    def model_not_found(_request, timeout):
        raise HTTPError("http://localhost/api/chat", 404, "not found", {}, None)

    monkeypatch.setattr(study_assistant_service, "urlopen", model_not_found)
    response = client.post(
        "/api/study-assistant/chat",
        json={"message": "Explain recursion."},
    )

    assert response.status_code == 503
    assert "ollama pull qwen2.5:1.5b" in response.json()["detail"]


def test_study_assistant_route_is_in_openapi(client):
    openapi = client.get("/openapi.json").json()
    assert "/api/study-assistant/chat" in openapi["paths"]
