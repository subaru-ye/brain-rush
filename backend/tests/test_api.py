from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as main_module
from app.llm import AiClientError
from app.services import LearningService


class ErrorAiClient:
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail

    def generate_quiz(self, input_text: str):
        raise AiClientError(self.code, self.detail)

    def generate_report(self, topic, questions, answers, accuracy):
        raise AiClientError(self.code, self.detail)


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]


def test_request_id_header_is_reused(client):
    response = client.get("/health", headers={"X-Request-ID": "test-request-id"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-request-id"


def test_generate_quiz_rejects_empty_input(client):
    response = client.post("/api/generate-quiz", json={"inputText": " "})

    assert response.status_code == 422


def test_generate_quiz_returns_five_valid_questions(client):
    response = client.post("/api/generate-quiz", json={"inputText": "AI Agent"})

    assert response.status_code == 200
    data = response.json()
    assert data["topic"] == "AI Agent"
    assert len(data["questions"]) == 5
    assert data["questions"][0]["answerIndex"] == 0
    assert data["questions"][0]["explanation"]


def test_generate_quiz_reports_invalid_ai_structure(invalid_quiz_client):
    response = invalid_quiz_client.post("/api/generate-quiz", json={"inputText": "AI Agent"})

    assert response.status_code == 502
    assert response.json()["code"] == "ai_invalid_response"
    assert response.json()["detail"]


def test_generate_report_returns_programmatic_score(client):
    quiz_response = client.post("/api/generate-quiz", json={"inputText": "AI Agent"})
    quiz = quiz_response.json()
    answers = [
        {"questionId": "q1", "selectedIndex": 0, "isCorrect": True, "elapsedMs": 1200},
        {"questionId": "q2", "selectedIndex": 1, "isCorrect": False, "elapsedMs": 1300},
        {"questionId": "q3", "selectedIndex": 0, "isCorrect": True, "elapsedMs": 1400},
        {"questionId": "q4", "selectedIndex": 0, "isCorrect": True, "elapsedMs": 1500},
        {"questionId": "q5", "selectedIndex": 0, "isCorrect": True, "elapsedMs": 1600},
    ]

    response = client.post(
        "/api/generate-report",
        json={"topic": quiz["topic"], "questions": quiz["questions"], "answers": answers},
    )

    assert response.status_code == 200
    report = response.json()["report"]
    assert report["score"] == 80
    assert report["accuracy"] == 80
    assert len(report["wrongQuestions"]) == 1
    assert report["wrongQuestions"][0]["questionId"] == "q2"
    assert report["suggestions"]


def test_generate_report_recomputes_score_when_frontend_is_correct_is_wrong(client):
    quiz_response = client.post("/api/generate-quiz", json={"inputText": "AI Agent"})
    quiz = quiz_response.json()
    answers = [
        {"questionId": "q1", "selectedIndex": 1, "isCorrect": True, "elapsedMs": 1200},
        {"questionId": "q2", "selectedIndex": 0, "isCorrect": False, "elapsedMs": 1300},
        {"questionId": "q3", "selectedIndex": 0, "isCorrect": False, "elapsedMs": 1400},
        {"questionId": "q4", "selectedIndex": 0, "isCorrect": True, "elapsedMs": 1500},
        {"questionId": "q5", "selectedIndex": 1, "isCorrect": True, "elapsedMs": 1600},
    ]

    response = client.post(
        "/api/generate-report",
        json={"topic": quiz["topic"], "questions": quiz["questions"], "answers": answers},
    )

    assert response.status_code == 200
    report = response.json()["report"]
    assert report["score"] == 60
    assert report["accuracy"] == 60
    assert [item["questionId"] for item in report["wrongQuestions"]] == ["q1", "q5"]


def test_generate_report_uses_recomputed_answer_for_wrong_question_review(client):
    quiz_response = client.post("/api/generate-quiz", json={"inputText": "AI Agent"})
    quiz = quiz_response.json()
    answers = [{"questionId": "q1", "selectedIndex": 1, "isCorrect": True, "elapsedMs": 1200}]

    response = client.post(
        "/api/generate-report",
        json={"topic": quiz["topic"], "questions": quiz["questions"], "answers": answers},
    )

    assert response.status_code == 200
    wrong_question = response.json()["report"]["wrongQuestions"][0]
    assert wrong_question["questionId"] == "q1"
    assert wrong_question["userAnswer"] == quiz["questions"][0]["options"][1]
    assert wrong_question["correctAnswer"] == quiz["questions"][0]["options"][0]


def test_generate_report_rejects_unknown_question_id(client):
    quiz_response = client.post("/api/generate-quiz", json={"inputText": "AI Agent"})
    quiz = quiz_response.json()

    response = client.post(
        "/api/generate-report",
        json={
            "topic": quiz["topic"],
            "questions": quiz["questions"],
            "answers": [{"questionId": "missing", "selectedIndex": 0, "isCorrect": True}],
        },
    )

    assert response.status_code == 422


def test_get_ai_client_is_cached(monkeypatch):
    class DummyAiClient:
        def __init__(self, settings):
            self.settings = settings

    main_module.get_ai_client.cache_clear()
    monkeypatch.setattr(main_module, "LangChainAiClient", DummyAiClient)

    try:
        first = main_module.get_ai_client()
        second = main_module.get_ai_client()
    finally:
        main_module.get_ai_client.cache_clear()

    assert first is second


def test_generate_report_reports_invalid_ai_structure(invalid_report_client):
    quiz = {
        "topic": "AI Agent",
        "questions": [
            {
                "id": f"q{i}",
                "stem": f"Question {i}",
                "options": ["A", "B", "C", "D"],
                "answerIndex": 0,
                "explanation": "Explanation",
                "knowledgePoint": "Knowledge Point",
            }
            for i in range(1, 6)
        ],
    }
    response = invalid_report_client.post(
        "/api/generate-report",
        json={
            "topic": quiz["topic"],
            "questions": quiz["questions"],
            "answers": [{"questionId": "q1", "selectedIndex": 1, "isCorrect": False}],
        },
    )

    assert response.status_code == 502
    assert response.json()["code"] == "ai_invalid_response"
    assert response.json()["detail"]


def test_generate_quiz_returns_timeout_error_code():
    main_module.app.dependency_overrides[main_module.get_learning_service] = lambda: LearningService(
        ErrorAiClient("ai_timeout", "AI 服务响应超时，请稍后重试")
    )
    try:
        with TestClient(main_module.app) as client:
            response = client.post(
                "/api/generate-quiz",
                json={"inputText": "AI Agent"},
                headers={"X-Request-ID": "quiz-timeout-request"},
            )
    finally:
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {
        "code": "ai_timeout",
        "detail": "AI 服务响应超时，请稍后重试",
    }
    assert response.headers["x-request-id"] == "quiz-timeout-request"


def test_generate_report_returns_rate_limit_error_code():
    main_module.app.dependency_overrides[main_module.get_learning_service] = lambda: LearningService(
        ErrorAiClient("ai_rate_limited", "AI 服务当前限流，请稍后重试")
    )
    try:
        with TestClient(main_module.app) as client:
            response = client.post(
                "/api/generate-report",
                json={
                    "topic": "AI Agent",
                    "questions": [
                        {
                            "id": "q1",
                            "stem": "Question 1",
                            "options": ["A", "B", "C", "D"],
                            "answerIndex": 0,
                            "explanation": "Explanation",
                            "knowledgePoint": "Knowledge Point",
                        }
                    ],
                    "answers": [{"questionId": "q1", "selectedIndex": 1, "isCorrect": False}],
                },
            )
    finally:
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {
        "code": "ai_rate_limited",
        "detail": "AI 服务当前限流，请稍后重试",
    }


def test_generate_quiz_returns_auth_error_when_ai_client_init_fails(monkeypatch):
    class RaisingAiClient:
        def __init__(self, settings):
            raise RuntimeError("OPENAI_API_KEY 未配置，无法调用 AI 服务")

    main_module.app.dependency_overrides.clear()
    main_module.get_ai_client.cache_clear()
    monkeypatch.setattr(main_module, "LangChainAiClient", RaisingAiClient)

    try:
        with TestClient(main_module.app) as client:
            response = client.post("/api/generate-quiz", json={"inputText": "AI Agent"})
    finally:
        main_module.get_ai_client.cache_clear()
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 502
    assert response.json() == {
        "code": "ai_auth_error",
        "detail": "OPENAI_API_KEY 未配置，无法调用 AI 服务",
    }
