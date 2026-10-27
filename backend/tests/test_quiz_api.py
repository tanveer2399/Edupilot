import json
from uuid import UUID

import pytest

from app.core.config import AUTH_COOKIE_NAME
from app.services import quiz_service
from app.services.quiz_service import QuizError
from app.services.study_assistant_service import (
    EMPTY_RESPONSE_DETAIL,
    OllamaResponse,
    StudyAssistantError,
)

def valid_quiz_data(count=5):
    return {
        "questions": [
            {
                "question_id": f"q{index}",
                "question": f"Question {index}?",
                "options": {
                    "A": f"Option {index} A",
                    "B": f"Option {index} B",
                    "C": f"Option {index} C",
                    "D": f"Option {index} D",
                },
                "correct_answer": "B",
                "explanation": f"Explanation {index}.",
            }
            for index in range(count)
        ]
    }


def mock_quiz_generation(monkeypatch, raw_response):
    async def fake_request(messages, response_format, **_kwargs):
        assert messages[0]["role"] == "system"
        assert "exactly 5 easy questions" in messages[1]["content"]
        assert response_format["type"] == "object"
        return raw_response

    monkeypatch.setattr(quiz_service, "_request_ollama", fake_request)


def valid_study_plan_data():
    return {
        "steps": [
            {
                "focus": f"Review concept {index}",
                "activity": f"Write and check a short explanation for concept {index}.",
                "minutes": 10,
            }
            for index in range(3)
        ]
    }


def create_submitted_quiz(client, monkeypatch, include_mistake=True):
    mock_quiz_generation(monkeypatch, json.dumps(valid_quiz_data()))
    generated = client.post(
        "/api/quiz/generate",
        json={"topic": "Python", "num_questions": 5},
    )
    quiz_id = generated.json()["quiz_id"]
    response = client.post(
        f"/api/quiz/{quiz_id}/submit",
        json={
            "answers": [
                {
                    "question_id": f"q{index}",
                    "selected_answer": (
                        "A" if include_mistake and index == 0 else "B"
                    ),
                }
                for index in range(5)
            ]
        },
    )
    assert response.status_code == 200
    return quiz_id


def test_generate_quiz_hides_answer_key(client, monkeypatch):
    mock_quiz_generation(monkeypatch, json.dumps(valid_quiz_data()))
    response = client.post(
        "/api/quiz/generate",
        json={
            "topic": "Python functions",
            "num_questions": 5,
            "difficulty": "easy",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["num_questions"] == 5
    assert body["difficulty"] == "easy"
    assert len(body["questions"]) == 5
    assert all(set(question["options"]) == {"A", "B", "C", "D"} for question in body["questions"])
    assert "correct_answer" not in response.text
    assert "explanation" not in response.text


def test_quiz_session_cannot_be_used_by_another_student(
    client,
    auth_env,
    monkeypatch,
):
    mock_quiz_generation(monkeypatch, json.dumps(valid_quiz_data()))
    generated = client.post(
        "/api/quiz/generate",
        json={"topic": "Python", "num_questions": 5},
    )
    quiz_id = generated.json()["quiz_id"]
    client.cookies.set(
        AUTH_COOKIE_NAME,
        auth_env["other_student_token"],
        path="/api",
    )

    response = client.post(
        f"/api/quiz/{quiz_id}/submit",
        json={
            "answers": [
                {"question_id": f"q{index}", "selected_answer": "B"}
                for index in range(5)
            ]
        },
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"topic": "", "notes": ""},
        {"topic": "Databases", "num_questions": 3},
        {"topic": "Databases", "difficulty": "extreme"},
        {"notes": "x" * 10001},
    ],
)
def test_generate_quiz_validates_request(client, payload):
    response = client.post("/api/quiz/generate", json=payload)
    assert response.status_code == 422


def test_generate_quiz_accepts_notes_without_topic(client, monkeypatch):
    async def fake_request(messages, response_format, **_kwargs):
        assert "Student-provided study notes" in messages[1]["content"]
        return json.dumps(valid_quiz_data())

    monkeypatch.setattr(quiz_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/quiz/generate",
        json={"notes": "A function can return a value.", "num_questions": 5},
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "raw_response",
    [
        "not JSON",
        "",
        '{"questions": [',
        json.dumps([valid_quiz_data()]),
        json.dumps(valid_quiz_data(4)),
        json.dumps(
            {
                **valid_quiz_data(),
                "questions": [
                    {
                        **valid_quiz_data()["questions"][0],
                        "options": {"A": "same", "B": "same", "C": "other", "D": "last"},
                    },
                    *valid_quiz_data()["questions"][1:],
                ],
            }
        ),
        json.dumps(
            {
                **valid_quiz_data(),
                "questions": [
                    valid_quiz_data()["questions"][0],
                    {
                        **valid_quiz_data()["questions"][1],
                        "question_id": "q0",
                    },
                    *valid_quiz_data()["questions"][2:],
                ],
            }
        ),
    ],
)
def test_generate_quiz_rejects_invalid_ai_output(client, monkeypatch, raw_response):
    request_count = 0

    async def fake_request(_messages, _response_format, **_kwargs):
        nonlocal request_count
        request_count += 1
        return raw_response

    monkeypatch.setattr(quiz_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/quiz/generate",
        json={"topic": "Python", "num_questions": 5},
    )
    assert response.status_code == 502
    assert "valid quiz" in response.json()["detail"]
    assert request_count == 2


def test_generate_quiz_diagnoses_duplicate_questions_without_logging_content(
    client,
    monkeypatch,
    caplog,
):
    duplicated_quiz = valid_quiz_data()
    duplicated_quiz["questions"][1]["question"] = duplicated_quiz["questions"][0]["question"]

    async def fake_request(_messages, _response_format, **_kwargs):
        return json.dumps(duplicated_quiz)

    monkeypatch.setattr(quiz_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/quiz/generate",
        json={"topic": "Python", "num_questions": 5},
    )

    assert response.status_code == 502
    assert "valid quiz" in response.json()["detail"]
    assert "duplicate_questions" in response.json()["detail"]
    assert "questions[1].question" in response.json()["detail"]
    assert caplog.text.count("reason=duplicate_questions") == 2
    assert "attempt=1" in caplog.text
    assert "attempt=2" in caplog.text
    assert "field_paths=('questions[1].question',)" in caplog.text
    assert "Question 0?" not in caplog.text


@pytest.mark.parametrize(
    "raw_response",
    [
        f"```json\n{json.dumps(valid_quiz_data())}\n```",
        (
            "Here is your quiz:\n"
            f"{json.dumps(valid_quiz_data())}\n"
            "Review your answers when finished."
        ),
    ],
)
def test_generate_quiz_accepts_fenced_json_and_surrounding_text(
    client,
    monkeypatch,
    raw_response,
):
    async def fake_request(_messages, _response_format, **_kwargs):
        return raw_response

    monkeypatch.setattr(quiz_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/quiz/generate",
        json={"topic": "Python", "num_questions": 5},
    )

    assert response.status_code == 200
    assert len(response.json()["questions"]) == 5


@pytest.mark.parametrize(
    "invalid_quiz",
    [
        {
            "questions": [
                {
                    key: value
                    for key, value in question.items()
                    if not (index == 0 and key == "explanation")
                }
                for index, question in enumerate(valid_quiz_data()["questions"])
            ]
        },
        {
            "questions": [
                "not a question object",
                *valid_quiz_data()["questions"][1:],
            ]
        },
        {
            "questions": [
                {
                    **question,
                    **(
                        {
                            "options": {
                                "A": "First",
                                "B": "Second",
                                "C": "Third",
                                "E": "Fourth",
                            }
                        }
                        if index == 0
                        else {}
                    ),
                }
                for index, question in enumerate(valid_quiz_data()["questions"])
            ]
        },
        {
            "questions": [
                {
                    **{
                        key: value
                        for key, value in question.items()
                        if not (index == 0 and key == "question")
                    },
                    **({"question_text": "Renamed question"} if index == 0 else {}),
                }
                for index, question in enumerate(valid_quiz_data()["questions"])
            ]
        },
        {
            "questions": [
                {
                    **question,
                    **({"correct_answer": "E"} if index == 0 else {}),
                }
                for index, question in enumerate(valid_quiz_data()["questions"])
            ]
        },
        {
            "questions": [
                {
                    **question,
                    **(
                        {"options": {"A": "one", "B": "one", "C": "three", "D": "four"}}
                        if index == 0
                        else {}
                    ),
                }
                for index, question in enumerate(valid_quiz_data()["questions"])
            ]
        },
        {
            "questions": [
                {
                    **question,
                    **({"question_id": 123} if index == 0 else {}),
                }
                for index, question in enumerate(valid_quiz_data()["questions"])
            ]
        },
    ],
    ids=[
        "missing-field",
        "invalid-correct-answer",
        "duplicate-options",
        "invalid-question-type",
        "invalid-option-keys",
        "wrong-field-type",
        "incorrectly-named-field",
    ],
)
def test_generate_quiz_rejects_schema_invalid_ai_output(
    client,
    monkeypatch,
    caplog,
    invalid_quiz,
):
    async def fake_request(_messages, _response_format, **_kwargs):
        return json.dumps(invalid_quiz)

    monkeypatch.setattr(quiz_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/quiz/generate",
        json={"topic": "Python", "num_questions": 5},
    )

    assert response.status_code == 502
    assert "valid quiz" in response.json()["detail"]
    assert "Rejected quiz output" in caplog.text
    assert "Question 0?" not in caplog.text


def test_generate_quiz_retries_invalid_ai_output(client, monkeypatch):
    responses = iter(["not JSON", json.dumps(valid_quiz_data())])

    async def fake_request(messages, _response_format, **_kwargs):
        if len(messages) > 2:
            assert "Attempt 1 was rejected: invalid_json" in messages[-1]["content"]
            assert "distinct questions" in messages[-1]["content"]
        return next(responses)

    monkeypatch.setattr(quiz_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/quiz/generate",
        json={"topic": "Python", "num_questions": 5},
    )

    assert response.status_code == 200
    assert len(response.json()["questions"]) == 5


def test_generate_quiz_retries_duplicate_options_with_more_varied_generation(
    client,
    monkeypatch,
):
    duplicate_options = valid_quiz_data()
    duplicate_options["questions"][0]["options"]["B"] = "Option 0 A"
    responses = iter([json.dumps(duplicate_options), json.dumps(valid_quiz_data())])
    temperatures = []

    async def fake_request(messages, _response_format, **kwargs):
        temperatures.append(kwargs.get("temperature", 0.3))
        if len(messages) > 2:
            assert "questions[0].options" in messages[-1]["content"]
            assert "four distinct texts" in messages[-1]["content"]
        return next(responses)

    monkeypatch.setattr(quiz_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/quiz/generate",
        json={"topic": "Python", "num_questions": 5},
    )

    assert response.status_code == 200
    assert len(response.json()["questions"]) == 5
    assert temperatures == [0.3, 0.7]


def test_generate_quiz_retries_duplicate_question_with_field_specific_guidance(
    client,
    monkeypatch,
):
    duplicated_quiz = valid_quiz_data()
    duplicated_quiz["questions"][1]["question"] = duplicated_quiz["questions"][0]["question"]
    responses = iter(
        [json.dumps(duplicated_quiz), json.dumps(valid_quiz_data())]
    )

    async def fake_request(messages, _response_format, **_kwargs):
        if len(messages) > 2:
            retry_prompt = messages[-1]["content"]
            assert "questions[1].question" in retry_prompt
            assert "different learning objective or operation" in retry_prompt
        return next(responses)

    monkeypatch.setattr(quiz_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/quiz/generate",
        json={"topic": "Python", "num_questions": 5},
    )

    assert response.status_code == 200
    assert len(response.json()["questions"]) == 5


def test_generate_quiz_logs_ollama_truncation_metadata(client, monkeypatch, caplog):
    async def fake_request(_messages, _response_format, **_kwargs):
        return OllamaResponse(
            content="not JSON",
            done_reason="length",
            eval_count=8192,
        )

    monkeypatch.setattr(quiz_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/quiz/generate",
        json={"topic": "Python", "num_questions": 5},
    )

    assert response.status_code == 502
    assert "truncated=True" in caplog.text
    assert "output_tokens=8192" in caplog.text


def test_generate_quiz_retries_provider_empty_response(client, monkeypatch):
    request_count = 0

    async def fake_request(messages, _response_format, **_kwargs):
        nonlocal request_count
        request_count += 1
        if request_count == 1:
            raise StudyAssistantError(502, EMPTY_RESPONSE_DETAIL)
        assert "previous response was empty" in messages[-1]["content"]
        return json.dumps(valid_quiz_data())

    monkeypatch.setattr(quiz_service, "_request_ollama", fake_request)
    response = client.post(
        "/api/quiz/generate",
        json={"topic": "Python", "num_questions": 5},
    )

    assert response.status_code == 200
    assert request_count == 2


def test_submit_quiz_scores_answers_and_unanswered_as_incorrect(client, monkeypatch):
    mock_quiz_generation(monkeypatch, json.dumps(valid_quiz_data()))
    generated = client.post(
        "/api/quiz/generate",
        json={"topic": "Python", "num_questions": 5},
    ).json()
    assert "correct_answer" not in str(generated)

    response = client.post(
        f"/api/quiz/{generated['quiz_id']}/submit",
        json={
            "answers": [
                {"question_id": "q0", "selected_answer": "B"},
                {"question_id": "q1", "selected_answer": "A"},
                {"question_id": "q2", "selected_answer": "B"},
            ]
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["total_questions"] == 5
    assert result["correct_answers"] == 2
    assert result["incorrect_answers"] == 3
    assert result["score_percentage"] == 40
    assert result["results"][0]["correct_answer"] == "B"
    assert result["results"][1]["selected_answer"] == "A"
    assert result["results"][3]["selected_answer"] is None
    assert result["results"][3]["is_correct"] is False
    assert result["results"][0]["explanation"] == "Explanation 0."


@pytest.mark.parametrize(
    ("answers", "correct", "incorrect", "percentage"),
    [
        ([{"question_id": f"q{i}", "selected_answer": "B"} for i in range(5)], 5, 0, 100),
        ([{"question_id": f"q{i}", "selected_answer": "A"} for i in range(5)], 0, 5, 0),
    ],
)
def test_submit_quiz_perfect_or_zero_score(
    client,
    monkeypatch,
    answers,
    correct,
    incorrect,
    percentage,
):
    mock_quiz_generation(monkeypatch, json.dumps(valid_quiz_data()))
    quiz_id = client.post(
        "/api/quiz/generate",
        json={"topic": "Python", "num_questions": 5},
    ).json()["quiz_id"]
    response = client.post(
        f"/api/quiz/{quiz_id}/submit",
        json={"answers": answers},
    )

    assert response.status_code == 200
    assert response.json()["correct_answers"] == correct
    assert response.json()["incorrect_answers"] == incorrect
    assert response.json()["score_percentage"] == percentage


def test_duplicate_submission_returns_original_result(client, monkeypatch):
    mock_quiz_generation(monkeypatch, json.dumps(valid_quiz_data()))
    quiz_id = client.post(
        "/api/quiz/generate",
        json={"topic": "Python", "num_questions": 5},
    ).json()["quiz_id"]
    original = client.post(
        f"/api/quiz/{quiz_id}/submit",
        json={"answers": [{"question_id": f"q{i}", "selected_answer": "B"} for i in range(5)]},
    )
    duplicate = client.post(
        f"/api/quiz/{quiz_id}/submit",
        json={"answers": [{"question_id": f"q{i}", "selected_answer": "A"} for i in range(5)]},
    )

    assert original.status_code == duplicate.status_code == 200
    assert duplicate.json() == original.json()


def test_submit_rejects_duplicate_or_unknown_question_ids(client, monkeypatch):
    mock_quiz_generation(monkeypatch, json.dumps(valid_quiz_data()))
    quiz_id = client.post(
        "/api/quiz/generate",
        json={"topic": "Python", "num_questions": 5},
    ).json()["quiz_id"]

    duplicate = client.post(
        f"/api/quiz/{quiz_id}/submit",
        json={
            "answers": [
                {"question_id": "q0", "selected_answer": "A"},
                {"question_id": "q0", "selected_answer": "B"},
            ]
        },
    )
    unknown = client.post(
        f"/api/quiz/{quiz_id}/submit",
        json={"answers": [{"question_id": "unknown", "selected_answer": "A"}]},
    )

    assert duplicate.status_code == 422
    assert unknown.status_code == 422


def test_submit_returns_not_found_for_expired_or_unknown_quiz(client):
    response = client.post(
        f"/api/quiz/{UUID(int=0)}/submit",
        json={"answers": []},
    )
    assert response.status_code == 404


def test_study_plan_uses_only_missed_answers(client, monkeypatch):
    quiz_id = create_submitted_quiz(client, monkeypatch)

    async def fake_request(messages, response_format):
        assert messages[0]["role"] == "system"
        assert "Question 0?" in messages[1]["content"]
        assert "Question 1?" not in messages[1]["content"]
        assert '"student_answer": "A. Option 0 A"' in messages[1]["content"]
        assert response_format["type"] == "object"
        return json.dumps(valid_study_plan_data())

    monkeypatch.setattr(quiz_service, "_request_ollama", fake_request)
    response = client.post(
        f"/api/quiz/{quiz_id}/study-plan",
        json={},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["quiz_id"] == quiz_id
    assert body["topic"] == "Python"
    assert len(body["steps"]) == 3
    assert body["steps"][0]["minutes"] == 10


@pytest.mark.parametrize(
    "raw_response",
    [
        f"```json\n{json.dumps(valid_study_plan_data())}\n```",
        (
            "Here is the requested review plan:\n"
            f"{json.dumps(valid_study_plan_data())}\n"
            "I hope this helps."
        ),
    ],
)
def test_study_plan_accepts_fenced_json_and_surrounding_text(
    client,
    monkeypatch,
    raw_response,
):
    quiz_id = create_submitted_quiz(client, monkeypatch)

    async def fake_request(_messages, _response_format):
        return raw_response

    monkeypatch.setattr(quiz_service, "_request_ollama", fake_request)
    response = client.post(f"/api/quiz/{quiz_id}/study-plan")

    assert response.status_code == 200
    assert len(response.json()["steps"]) == 3


def test_study_plan_handles_ollama_response_metadata(client, monkeypatch):
    quiz_id = create_submitted_quiz(client, monkeypatch)

    async def fake_request(_messages, _response_format):
        return OllamaResponse(
            content=json.dumps(valid_study_plan_data()),
            done_reason="stop",
            eval_count=128,
        )

    monkeypatch.setattr(quiz_service, "_request_ollama", fake_request)
    response = client.post(f"/api/quiz/{quiz_id}/study-plan")

    assert response.status_code == 200
    assert len(response.json()["steps"]) == 3


def test_study_plan_requires_submitted_quiz(client, monkeypatch):
    mock_quiz_generation(monkeypatch, json.dumps(valid_quiz_data()))
    quiz_id = client.post(
        "/api/quiz/generate",
        json={"topic": "Python", "num_questions": 5},
    ).json()["quiz_id"]

    response = client.post(f"/api/quiz/{quiz_id}/study-plan")

    assert response.status_code == 409
    assert "Submit this quiz" in response.json()["detail"]


def test_study_plan_rejects_quiz_without_missed_answers(client, monkeypatch):
    quiz_id = create_submitted_quiz(
        client,
        monkeypatch,
        include_mistake=False,
    )

    response = client.post(f"/api/quiz/{quiz_id}/study-plan")

    assert response.status_code == 422
    assert "no missed answers" in response.json()["detail"]


def test_study_plan_reports_unknown_quiz(client):
    response = client.post(
        f"/api/quiz/{UUID(int=0)}/study-plan",
    )

    assert response.status_code == 404


def test_study_plan_retries_invalid_ai_output(client, monkeypatch, caplog):
    quiz_id = create_submitted_quiz(client, monkeypatch)
    responses = iter(["", json.dumps(valid_study_plan_data())])
    request_count = 0

    async def fake_request(messages, _response_format):
        nonlocal request_count
        request_count += 1
        if request_count == 2:
            assert "did not satisfy the study plan requirements" in messages[-1]["content"]
        return next(responses)

    monkeypatch.setattr(quiz_service, "_request_ollama", fake_request)
    response = client.post(f"/api/quiz/{quiz_id}/study-plan")

    assert response.status_code == 200
    assert request_count == 2
    assert "reason=empty_response" in caplog.text
    assert "opening_braces=0" in caplog.text


def test_study_plan_retries_provider_empty_response(client, monkeypatch):
    quiz_id = create_submitted_quiz(client, monkeypatch)
    request_count = 0

    async def fake_request(messages, _response_format):
        nonlocal request_count
        request_count += 1
        if request_count == 1:
            raise StudyAssistantError(502, EMPTY_RESPONSE_DETAIL)
        assert "previous response was empty" in messages[-1]["content"]
        return json.dumps(valid_study_plan_data())

    monkeypatch.setattr(quiz_service, "_request_ollama", fake_request)
    response = client.post(f"/api/quiz/{quiz_id}/study-plan")

    assert response.status_code == 200
    assert request_count == 2


@pytest.mark.parametrize(
    ("raw_response", "reason"),
    [
        ("", "empty_response"),
        ("not JSON", "invalid_json"),
        ('{"steps":[', "truncated_json"),
    ],
)
def test_study_plan_reports_malformed_output_safely(
    client,
    monkeypatch,
    caplog,
    raw_response,
    reason,
):
    quiz_id = create_submitted_quiz(client, monkeypatch)
    request_count = 0

    async def fake_request(_messages, _response_format):
        nonlocal request_count
        request_count += 1
        return raw_response

    monkeypatch.setattr(quiz_service, "_request_ollama", fake_request)
    response = client.post(f"/api/quiz/{quiz_id}/study-plan")

    assert response.status_code == 502
    assert "valid review plan" in response.json()["detail"]
    assert request_count == 2
    assert "Rejected study plan output" in caplog.text
    assert f"reason={reason}" in caplog.text
    if raw_response:
        assert raw_response not in caplog.text


@pytest.mark.parametrize(
    "invalid_plan",
    [
        {
            "steps": [
                {
                    "focus": (
                        "private generated phrase"
                        if index == 0
                        else f"Review concept {index}"
                    ),
                    "minutes": 10,
                }
                for index in range(3)
            ]
        },
        {
            "steps": [
                {
                    "focus": f"Review concept {index}",
                    "activity": f"Write and check a short explanation for concept {index}.",
                    "minutes": 21,
                }
                for index in range(3)
            ]
        },
        {
            "steps": [
                {
                    "focus": f"Review concept {index}",
                    "activity": f"Write and check a short explanation for concept {index}.",
                    "minutes": 20,
                }
                for index in range(4)
            ]
        },
        {
            "steps": [
                {
                    "focus": f"Review concept {index}",
                    "activity": f"Write and check a short explanation for concept {index}.",
                    "minutes": "10",
                }
                for index in range(3)
            ]
        },
    ],
    ids=["missing-field", "invalid-step-duration", "total-over-60", "wrong-duration-type"],
)
def test_study_plan_returns_safe_error_for_invalid_ai_output(
    client,
    monkeypatch,
    caplog,
    invalid_plan,
):
    quiz_id = create_submitted_quiz(client, monkeypatch)
    request_count = 0

    async def fake_request(_messages, _response_format):
        nonlocal request_count
        request_count += 1
        return json.dumps(invalid_plan)

    monkeypatch.setattr(quiz_service, "_request_ollama", fake_request)
    response = client.post(f"/api/quiz/{quiz_id}/study-plan")

    assert response.status_code == 502
    assert "valid review plan" in response.json()["detail"]
    assert request_count == 2
    assert "Rejected study plan output" in caplog.text
    assert "private generated phrase" not in caplog.text


def test_study_plan_returns_safe_provider_error(client, monkeypatch):
    quiz_id = create_submitted_quiz(client, monkeypatch)

    async def failed_request(_messages, _response_format):
        raise StudyAssistantError(503, "Could not reach Ollama.")

    monkeypatch.setattr(quiz_service, "_request_ollama", failed_request)
    response = client.post(f"/api/quiz/{quiz_id}/study-plan")

    assert response.status_code == 503
    assert response.json() == {"detail": "Could not reach Ollama."}


def test_generation_returns_safe_provider_error(client, monkeypatch):
    async def failed_request(_messages, _response_format):
        raise StudyAssistantError(503, "Could not reach Ollama.")

    monkeypatch.setattr(quiz_service, "_request_ollama", failed_request)
    response = client.post(
        "/api/quiz/generate",
        json={"topic": "Python", "num_questions": 5},
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "Could not reach Ollama."}


def test_quiz_routes_are_documented(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/quiz/generate" in paths
    assert "/api/quiz/{quiz_id}/submit" in paths
    assert "/api/quiz/{quiz_id}/study-plan" in paths
