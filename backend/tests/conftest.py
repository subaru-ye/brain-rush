from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.llm import AiQuizDraft, AiReportDraft
from app.main import app, get_learning_service
from app.rate_limit import generation_rate_limiter
from app.schemas import QuizQuestion, UserAnswer
from app.services import LearningService


class FakeAiClient:
    def __init__(self, mode: str = "ok"):
        self.mode = mode

    def generate_quiz(self, input_text: str) -> AiQuizDraft:
        if self.mode == "invalid_quiz":
            return AiQuizDraft(topic="坏数据", questions=[])  # type: ignore[arg-type]
        questions = [
            QuizQuestion(
                id=f"q{i}",
                stem=f"第 {i} 题：{input_text} 的关键点是什么？",
                options=["概念理解", "随便猜测", "只背答案", "跳过学习"],
                answerIndex=0,
                explanation="核心是理解概念，再用题目检查掌握程度。",
                knowledgePoint="概念理解",
            )
            for i in range(1, 6)
        ]
        return AiQuizDraft(topic=input_text, questions=questions)

    def generate_report(
        self,
        topic: str,
        questions: list[QuizQuestion],
        answers: list[UserAnswer],
        accuracy: int,
    ) -> AiReportDraft:
        if self.mode == "invalid_report":
            return AiReportDraft(summary="", weakPoints=[], suggestions=[])  # type: ignore[arg-type]
        return AiReportDraft(
            summary=f"你已经完成 {topic} 的基础闯关，正确率为 {accuracy}%。",
            weakPoints=["概念理解"] if accuracy < 100 else [],
            suggestions=["复习错题解析", "再挑战一次同主题题目"],
        )


@pytest.fixture(autouse=True)
def clear_rate_limiter():
    generation_rate_limiter.clear()
    yield
    generation_rate_limiter.clear()


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_learning_service] = lambda: LearningService(FakeAiClient())
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def invalid_quiz_client() -> TestClient:
    app.dependency_overrides[get_learning_service] = lambda: LearningService(
        FakeAiClient(mode="invalid_quiz")
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def invalid_report_client() -> TestClient:
    app.dependency_overrides[get_learning_service] = lambda: LearningService(
        FakeAiClient(mode="invalid_report")
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
