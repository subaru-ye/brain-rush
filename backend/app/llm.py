from __future__ import annotations

import json
import re
import time
from typing import Any, TypeVar

from langchain_openai import ChatOpenAI
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)
from pydantic import BaseModel, Field, ValidationError

from .config import Settings
from .observability import log_event
from .prompts import (
    QUIZ_PROMPT_VERSION,
    REPORT_PROMPT_VERSION,
    build_quiz_prompt,
    build_report_prompt,
)
from .quiz_answers import format_option_indexes, is_answer_correct
from .schemas import QuizQuestion, UserAnswer


class AiQuizDraft(BaseModel):
    topic: str = Field(min_length=1, max_length=120)
    questions: list[QuizQuestion] = Field(min_length=1, max_length=5)


class AiReportDraft(BaseModel):
    summary: str = Field(min_length=1, max_length=800)
    weakPoints: list[str] = Field(default_factory=list, max_length=5)
    suggestions: list[str] = Field(default_factory=list, max_length=5)


class AiClientError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


TModel = TypeVar("TModel", bound=BaseModel)


def parse_json_model(content: object, model: type[TModel]) -> TModel:
    if isinstance(content, str):
        raw_text = content.strip()
    else:
        raw_text = json.dumps(content, ensure_ascii=False)

    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_text, re.DOTALL)
    if fence_match:
        raw_text = fence_match.group(1).strip()

    if not raw_text.startswith("{"):
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start >= 0 and end > start:
            raw_text = raw_text[start : end + 1]

    return model.model_validate_json(raw_text)


class LangChainAiClient:
    def __init__(self, settings: Settings, llm: Any | None = None):
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY 未配置，无法调用 AI 服务")

        self.model_name = settings.openai_model
        self.base_url = settings.openai_base_url
        self.timeout_seconds = settings.openai_timeout_seconds
        self.max_retries = settings.openai_max_retries
        self.quiz_prompt_version = QUIZ_PROMPT_VERSION
        self.report_prompt_version = REPORT_PROMPT_VERSION
        self.llm = llm or ChatOpenAI(
            api_key=settings.openai_api_key,
            base_url=self.base_url,
            model=self.model_name,
            temperature=0.4,
            timeout=self.timeout_seconds,
            max_retries=self.max_retries,
        )

    def generate_quiz(
        self,
        input_text: str,
        *,
        retrieved_context: str | None = None,
        question_count: int = 5,
    ) -> AiQuizDraft:
        return self._invoke_structured_prompt(
            operation="generate_quiz",
            prompt_version=self.quiz_prompt_version,
            prompt=build_quiz_prompt(),
            payload={
                "input_text": input_text,
                "retrieved_context": retrieved_context or "None",
                "question_count": question_count,
            },
            model=AiQuizDraft,
            invalid_response_detail="AI 返回的题目结构不合法，请稍后重试",
        )

    def generate_report(
        self,
        topic: str,
        questions: list[QuizQuestion],
        answers: list[UserAnswer],
        accuracy: int,
    ) -> AiReportDraft:
        wrong_points = []
        answer_by_question = {answer.questionId: answer for answer in answers}
        for question in questions:
            answer = answer_by_question.get(question.id)
            if answer and not is_answer_correct(question, answer):
                wrong_points.append(
                    {
                        "stem": question.stem,
                        "knowledgePoint": question.knowledgePoint,
                        "correctAnswer": format_option_indexes(
                            question.options,
                            question.answerIndexes,
                        ),
                        "explanation": question.explanation,
                    }
                )

        return self._invoke_structured_prompt(
            operation="generate_report",
            prompt_version=self.report_prompt_version,
            prompt=build_report_prompt(),
            payload={
                "topic": topic,
                "accuracy": accuracy,
                "wrong_points": wrong_points,
            },
            model=AiReportDraft,
            invalid_response_detail="AI 返回的复盘报告结构不合法，请稍后重试",
        )

    def _invoke_structured_prompt(
        self,
        *,
        operation: str,
        prompt_version: str,
        prompt: Any,
        payload: dict[str, Any],
        model: type[TModel],
        invalid_response_detail: str,
    ) -> TModel:
        started_at = time.perf_counter()
        chain = prompt | self.llm.with_structured_output(
            model,
            method="json_mode",
            include_raw=True,
        )

        try:
            result = chain.invoke(payload)
            parsed_result = self._extract_result(
                result=result,
                model=model,
                invalid_response_detail=invalid_response_detail,
            )
        except Exception as exc:
            classified = self._classify_exception(exc, invalid_response_detail)
            log_event(
                "ai_call_failed",
                operation=operation,
                prompt_version=prompt_version,
                model=self.model_name,
                base_url=self.base_url,
                timeout_seconds=self.timeout_seconds,
                max_retries=self.max_retries,
                duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
                code=classified.code,
            )
            if classified is exc:
                raise classified
            raise classified from exc

        log_event(
            "ai_call_completed",
            operation=operation,
            prompt_version=prompt_version,
            model=self.model_name,
            base_url=self.base_url,
            timeout_seconds=self.timeout_seconds,
            max_retries=self.max_retries,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )
        return parsed_result

    def _extract_result(
        self,
        *,
        result: object,
        model: type[TModel],
        invalid_response_detail: str,
    ) -> TModel:
        if not isinstance(result, dict):
            return self._validate_parsed_result(
                parsed=result,
                model=model,
                invalid_response_detail=invalid_response_detail,
            )

        parsed = result.get("parsed")
        if parsed is not None:
            return self._validate_parsed_result(
                parsed=parsed,
                model=model,
                invalid_response_detail=invalid_response_detail,
            )

        raw_message = result.get("raw")
        raw_content = getattr(raw_message, "content", raw_message)
        parsing_error = result.get("parsing_error")

        if self._is_empty_content(raw_content):
            raise AiClientError("ai_invalid_response", invalid_response_detail) from (
                parsing_error if isinstance(parsing_error, BaseException) else None
            )

        try:
            return parse_json_model(raw_content, model)
        except (ValidationError, ValueError, TypeError) as exc:
            raise AiClientError("ai_invalid_response", invalid_response_detail) from (
                parsing_error if isinstance(parsing_error, BaseException) else exc
            )

    @staticmethod
    def _validate_parsed_result(
        *,
        parsed: object,
        model: type[TModel],
        invalid_response_detail: str,
    ) -> TModel:
        try:
            if isinstance(parsed, model):
                return parsed
            return model.model_validate(parsed)
        except (ValidationError, ValueError, TypeError) as exc:
            raise AiClientError("ai_invalid_response", invalid_response_detail) from exc

    @staticmethod
    def _is_empty_content(content: object) -> bool:
        if content is None:
            return True
        if isinstance(content, str):
            return not content.strip()
        if isinstance(content, list):
            return len(content) == 0
        return False

    @staticmethod
    def _classify_exception(exc: Exception, invalid_response_detail: str) -> AiClientError:
        if isinstance(exc, AiClientError):
            return exc
        if isinstance(exc, AuthenticationError):
            return AiClientError("ai_auth_error", "AI 服务鉴权失败，请检查 API Key 配置")
        if isinstance(exc, RateLimitError):
            return AiClientError("ai_rate_limited", "AI 服务当前限流，请稍后重试")
        if isinstance(exc, APITimeoutError):
            return AiClientError("ai_timeout", "AI 服务响应超时，请稍后重试")
        if isinstance(exc, APIConnectionError):
            return AiClientError("ai_connection_error", "AI 服务连接失败，请稍后重试")
        if isinstance(exc, APIStatusError):
            return AiClientError("ai_upstream_error", "AI 服务暂时不可用，请稍后重试")
        if isinstance(exc, (ValidationError, ValueError, TypeError)):
            return AiClientError("ai_invalid_response", invalid_response_detail)
        return AiClientError("ai_upstream_error", "AI 服务暂时不可用，请稍后重试")
