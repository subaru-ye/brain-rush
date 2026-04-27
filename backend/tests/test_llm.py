from __future__ import annotations

import httpx
import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

import app.llm as llm_module
from app.config import Settings
from app.llm import AiClientError, AiQuizDraft, LangChainAiClient
from app.schemas import QuizQuestion


class FakeStructuredLlm:
    def __init__(self, *, result=None, error: Exception | None = None):
        self.result = result
        self.error = error

    def with_structured_output(self, schema, *, method, include_raw, **kwargs):
        assert method == "json_mode"
        assert include_raw is True

        if self.error is not None:
            def raise_error(_):
                raise self.error

            return RunnableLambda(raise_error)

        return RunnableLambda(lambda _: self.result)


def build_settings() -> Settings:
    return Settings(
        OPENAI_API_KEY="sk-test",
        OPENAI_BASE_URL="https://api.deepseek.com",
        OPENAI_MODEL="deepseek-v4-flash",
    )


def build_quiz_draft(topic: str = "AI Agent") -> AiQuizDraft:
    questions = [
        QuizQuestion(
            id=f"q{i}",
            stem=f"Question {i}",
            options=["A", "B", "C", "D"],
            answerIndex=0,
            explanation="Explanation",
            knowledgePoint="Knowledge Point",
        )
        for i in range(1, 6)
    ]
    return AiQuizDraft(topic=topic, questions=questions)


@pytest.fixture
def prompt_stub(monkeypatch):
    monkeypatch.setattr(llm_module, "build_quiz_prompt", lambda: RunnableLambda(lambda payload: payload))


def test_generate_quiz_uses_structured_output_success(prompt_stub):
    draft = build_quiz_draft()
    client = LangChainAiClient(
        build_settings(),
        llm=FakeStructuredLlm(
            result={"raw": AIMessage(content=""), "parsed": draft, "parsing_error": None}
        ),
    )

    result = client.generate_quiz("AI Agent")

    assert result == draft


def test_generate_quiz_falls_back_to_raw_json_when_structured_parse_fails(prompt_stub):
    draft = build_quiz_draft()
    client = LangChainAiClient(
        build_settings(),
        llm=FakeStructuredLlm(
            result={
                "raw": AIMessage(content=draft.model_dump_json()),
                "parsed": None,
                "parsing_error": ValueError("structured parsing failed"),
            }
        ),
    )

    result = client.generate_quiz("AI Agent")

    assert result == draft


def test_generate_quiz_returns_invalid_response_for_empty_raw_content(prompt_stub):
    client = LangChainAiClient(
        build_settings(),
        llm=FakeStructuredLlm(
            result={
                "raw": AIMessage(content=""),
                "parsed": None,
                "parsing_error": ValueError("empty content"),
            }
        ),
    )

    with pytest.raises(AiClientError) as exc_info:
        client.generate_quiz("AI Agent")

    assert exc_info.value.code == "ai_invalid_response"


def test_generate_quiz_returns_invalid_response_for_invalid_parsed_payload(prompt_stub):
    client = LangChainAiClient(
        build_settings(),
        llm=FakeStructuredLlm(
            result={
                "raw": AIMessage(content=""),
                "parsed": {"topic": "bad", "questions": []},
                "parsing_error": None,
            }
        ),
    )

    with pytest.raises(AiClientError) as exc_info:
        client.generate_quiz("AI Agent")

    assert exc_info.value.code == "ai_invalid_response"


@pytest.mark.parametrize(
    ("error", "expected_code"),
    [
        (
            AuthenticationError(
                "auth failed",
                response=httpx.Response(
                    401,
                    request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"),
                ),
                body={"error": "invalid_api_key"},
            ),
            "ai_auth_error",
        ),
        (
            RateLimitError(
                "rate limited",
                response=httpx.Response(
                    429,
                    request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"),
                ),
                body={"error": "rate_limit"},
            ),
            "ai_rate_limited",
        ),
        (
            APITimeoutError(
                request=httpx.Request("POST", "https://api.deepseek.com/chat/completions")
            ),
            "ai_timeout",
        ),
        (
            APIConnectionError(
                request=httpx.Request("POST", "https://api.deepseek.com/chat/completions")
            ),
            "ai_connection_error",
        ),
        (
            APIStatusError(
                "server error",
                response=httpx.Response(
                    500,
                    request=httpx.Request("POST", "https://api.deepseek.com/chat/completions"),
                ),
                body={"error": "server_error"},
            ),
            "ai_upstream_error",
        ),
    ],
)
def test_generate_quiz_classifies_openai_errors(prompt_stub, error, expected_code):
    client = LangChainAiClient(build_settings(), llm=FakeStructuredLlm(error=error))

    with pytest.raises(AiClientError) as exc_info:
        client.generate_quiz("AI Agent")

    assert exc_info.value.code == expected_code
