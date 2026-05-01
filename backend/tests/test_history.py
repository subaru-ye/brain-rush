from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main as main_module
from app.database import Base
from app import models  # noqa: F401


@pytest.fixture
def history_client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[main_module.get_db] = override_db
    with TestClient(main_module.app) as client:
        yield client
    main_module.app.dependency_overrides.clear()


def auth_headers(client: TestClient, code: str = "dev-code") -> dict[str, str]:
    response = client.post("/api/auth/wechat", json={"code": code})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def history_payload(session_id: str = "session-1") -> dict:
    questions = [
        {
            "id": "q1",
            "stem": "Question 1",
            "options": ["A", "B", "C", "D"],
            "answerIndex": 0,
            "explanation": "Explanation 1",
            "knowledgePoint": "Point 1",
        },
        {
            "id": "q2",
            "stem": "Question 2",
            "options": ["A", "B", "C", "D"],
            "answerIndex": 1,
            "explanation": "Explanation 2",
            "knowledgePoint": "Point 2",
        },
    ]
    return {
        "sessionId": session_id,
        "topic": "AI Agent",
        "questions": questions,
        "answers": [
            {"questionId": "q1", "selectedIndex": 0, "isCorrect": True},
            {"questionId": "q2", "selectedIndex": 0, "isCorrect": False},
        ],
        "report": {
            "score": 50,
            "accuracy": 50,
            "summary": "Summary",
            "weakPoints": ["Point 2"],
            "wrongQuestions": [
                {
                    "questionId": "q2",
                    "stem": "Question 2",
                    "userAnswer": "A",
                    "correctAnswer": "B",
                    "explanation": "Explanation 2",
                    "knowledgePoint": "Point 2",
                }
            ],
            "suggestions": ["Review"],
        },
    }


def test_history_requires_auth(history_client):
    response = history_client.get("/api/history")

    assert response.status_code == 401
    assert response.json()["code"] == "auth_required"


def test_question_feedback_requires_auth(history_client):
    payload = history_payload()
    response = history_client.post(
        "/api/question-feedback",
        json={
            "sessionId": payload["sessionId"],
            "topic": payload["topic"],
            "questionId": "q1",
            "reason": "question_inaccurate",
            "questionSnapshot": payload["questions"][0],
            "selectedIndex": 0,
            "sourcePage": "quiz",
        },
    )

    assert response.status_code == 401
    assert response.json()["code"] == "auth_required"


def test_wrong_questions_requires_auth(history_client):
    response = history_client.get("/api/wrong-questions")

    assert response.status_code == 401
    assert response.json()["code"] == "auth_required"


def test_create_list_and_get_history_record(history_client):
    headers = auth_headers(history_client)

    create_response = history_client.post(
        "/api/history",
        json=history_payload(),
        headers=headers,
    )
    assert create_response.status_code == 200
    record = create_response.json()["record"]
    assert record["topic"] == "AI Agent"
    assert record["score"] == 50
    assert record["accuracy"] == 50

    list_response = history_client.get("/api/history", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()["records"]) == 1

    detail_response = history_client.get(f"/api/history/{record['id']}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["questions"][1]["knowledgePoint"] == "Point 2"


def test_create_question_feedback_and_deduplicate(history_client):
    headers = auth_headers(history_client)
    payload = history_payload()
    feedback_payload = {
        "sessionId": payload["sessionId"],
        "topic": payload["topic"],
        "questionId": "q2",
        "reason": "explanation_unclear",
        "questionSnapshot": payload["questions"][1],
        "selectedIndex": 0,
        "sourcePage": "report",
    }

    first = history_client.post("/api/question-feedback", json=feedback_payload, headers=headers)
    second = history_client.post("/api/question-feedback", json=feedback_payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_history_records_are_user_scoped(history_client):
    user_a_headers = auth_headers(history_client, "user-a")
    user_b_headers = auth_headers(history_client, "user-b")

    response = history_client.post(
        "/api/history",
        json=history_payload(),
        headers=user_a_headers,
    )
    assert response.status_code == 200

    user_b_list = history_client.get("/api/history", headers=user_b_headers)
    assert user_b_list.status_code == 200
    assert user_b_list.json()["records"] == []


def test_wrong_questions_are_aggregated_and_user_scoped(history_client):
    user_a_headers = auth_headers(history_client, "user-a")
    user_b_headers = auth_headers(history_client, "user-b")

    response = history_client.post(
        "/api/history",
        json=history_payload(),
        headers=user_a_headers,
    )
    assert response.status_code == 200

    user_a_wrong = history_client.get("/api/wrong-questions", headers=user_a_headers)
    user_b_wrong = history_client.get("/api/wrong-questions", headers=user_b_headers)

    assert user_a_wrong.status_code == 200
    assert len(user_a_wrong.json()["items"]) == 1
    assert user_a_wrong.json()["items"][0]["questionId"] == "q2"
    assert user_a_wrong.json()["items"][0]["selectedIndex"] == 0
    assert user_b_wrong.status_code == 200
    assert user_b_wrong.json()["items"] == []
