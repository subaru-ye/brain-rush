from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app, get_ai_client


# 手动测试默认学习内容：直接改这里，就能调整发给大模型的出题主题。
# 也可以不改代码，在运行前设置环境变量 REAL_API_QUIZ_INPUT 覆盖它。
DEFAULT_QUIZ_INPUT = "AI Agent core concepts, tool calling, planning, and memory"


def test_generate_quiz_with_real_ai():
    settings = get_settings()
    if not settings.openai_api_key or settings.openai_api_key.startswith("sk-your-"):
        pytest.skip("OPENAI_API_KEY is not configured")

    app.dependency_overrides.clear()
    get_ai_client.cache_clear()
    try:
        input_text = os.getenv("REAL_API_QUIZ_INPUT", DEFAULT_QUIZ_INPUT)
        with TestClient(app) as client:
            response = client.post(
                "/api/generate-quiz",
                json={"inputText": input_text},
            )
    finally:
        get_ai_client.cache_clear()
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text

    data = response.json()
    print(json.dumps(data, ensure_ascii=False, indent=2))

    assert data["sessionId"]
    assert data["topic"]
    assert len(data["questions"]) == 5
    for question in data["questions"]:
        assert question["id"]
        assert question["stem"]
        assert len(question["options"]) == 4
        assert 0 <= question["answerIndex"] < len(question["options"])
        assert question["explanation"]
        assert question["knowledgePoint"]
