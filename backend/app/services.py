from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from pydantic import ValidationError

from .llm import AiClientError, AiQuizDraft, AiReportDraft
from .prompts import QUIZ_PROMPT_VERSION, REPORT_PROMPT_VERSION
from .schemas import (
    GenerateQuizResponse,
    GenerateReportRequest,
    GenerateReportResponse,
    QuizQuestion,
    ReviewReport,
    UserAnswer,
    WrongQuestionReview,
)


class AiClient(Protocol):
    def generate_quiz(self, input_text: str) -> AiQuizDraft:
        ...

    def generate_report(
        self,
        topic: str,
        questions: list[QuizQuestion],
        answers: list[UserAnswer],
        accuracy: int,
    ) -> AiReportDraft:
        ...


class AiServiceError(RuntimeError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass
class LearningService:
    ai_client: AiClient

    def generate_quiz(self, input_text: str) -> GenerateQuizResponse:
        try:
            draft = self.ai_client.generate_quiz(input_text)
            return GenerateQuizResponse(
                sessionId=uuid4().hex,
                topic=draft.topic.strip(),
                questions=draft.questions,
                quizPromptVersion=getattr(self.ai_client, "quiz_prompt_version", QUIZ_PROMPT_VERSION),
                quizModelName=getattr(self.ai_client, "model_name", ""),
            )
        except AiClientError as exc:
            raise AiServiceError(exc.code, exc.detail) from exc
        except (ValidationError, ValueError) as exc:
            raise AiServiceError("ai_invalid_response", "AI 返回的题目结构不合法，请稍后重试") from exc
        except Exception as exc:
            raise AiServiceError("ai_upstream_error", "AI 题目生成失败，请稍后重试") from exc

    def generate_report(self, request: GenerateReportRequest) -> GenerateReportResponse:
        total = len(request.answers)
        question_by_id = {question.id: question for question in request.questions}
        correct_count = sum(
            1
            for answer in request.answers
            if self._is_answer_correct(question_by_id[answer.questionId], answer)
        )
        accuracy = round(correct_count / total * 100) if total else 0
        score = accuracy

        try:
            draft = self.ai_client.generate_report(
                topic=request.topic,
                questions=request.questions,
                answers=request.answers,
                accuracy=accuracy,
            )
        except AiClientError as exc:
            raise AiServiceError(exc.code, exc.detail) from exc
        except (ValidationError, ValueError) as exc:
            raise AiServiceError("ai_invalid_response", "AI 返回的复盘报告结构不合法，请稍后重试") from exc
        except Exception as exc:
            raise AiServiceError("ai_upstream_error", "AI 复盘报告生成失败，请稍后重试") from exc

        report = ReviewReport(
            score=score,
            accuracy=accuracy,
            summary=draft.summary,
            weakPoints=draft.weakPoints,
            wrongQuestions=self._build_wrong_question_reviews(request, question_by_id),
            suggestions=draft.suggestions,
        )
        return GenerateReportResponse(
            report=report,
            reportPromptVersion=getattr(
                self.ai_client,
                "report_prompt_version",
                REPORT_PROMPT_VERSION,
            ),
            reportModelName=getattr(self.ai_client, "model_name", ""),
        )

    @staticmethod
    def _is_answer_correct(question: QuizQuestion, answer: UserAnswer) -> bool:
        return answer.selectedIndex == question.answerIndex

    @classmethod
    def _build_wrong_question_reviews(
        cls,
        request: GenerateReportRequest,
        question_by_id: dict[str, QuizQuestion],
    ) -> list[WrongQuestionReview]:
        answer_by_question = {answer.questionId: answer for answer in request.answers}
        wrong_reviews: list[WrongQuestionReview] = []

        for question in request.questions:
            answer = answer_by_question.get(question.id)
            if not answer or cls._is_answer_correct(question_by_id[question.id], answer):
                continue
            selected = question.options[answer.selectedIndex]
            correct = question.options[question.answerIndex]
            wrong_reviews.append(
                WrongQuestionReview(
                    questionId=question.id,
                    stem=question.stem,
                    userAnswer=selected,
                    correctAnswer=correct,
                    explanation=question.explanation,
                    knowledgePoint=question.knowledgePoint,
                )
            )
        return wrong_reviews
