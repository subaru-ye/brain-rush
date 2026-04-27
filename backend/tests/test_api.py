from __future__ import annotations


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
    assert "题目结构不合法" in response.json()["detail"]


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


def test_generate_report_reports_invalid_ai_structure(invalid_report_client):
    quiz = {
        "topic": "AI Agent",
        "questions": [
            {
                "id": f"q{i}",
                "stem": f"第 {i} 题",
                "options": ["A", "B", "C", "D"],
                "answerIndex": 0,
                "explanation": "讲解",
                "knowledgePoint": "知识点",
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
    assert "复盘报告结构不合法" in response.json()["detail"]
