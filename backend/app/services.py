from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from pydantic import ValidationError

from .llm import AiQuizDraft, AiReportDraft
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
    pass


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
            )
        except (ValidationError, ValueError) as exc:
            raise AiServiceError("AI 返回的题目结构不合法，请稍后重试") from exc
        except Exception as exc:
            raise AiServiceError(f"AI 题目生成失败：{exc}") from exc

    def generate_report(self, request: GenerateReportRequest) -> GenerateReportResponse:
        total = len(request.answers)
        correct_count = sum(1 for answer in request.answers if answer.isCorrect)
        accuracy = round(correct_count / total * 100) if total else 0
        score = accuracy

        try:
            draft = self.ai_client.generate_report(
                topic=request.topic,
                questions=request.questions,
                answers=request.answers,
                accuracy=accuracy,
            )
        except (ValidationError, ValueError) as exc:
            raise AiServiceError("AI 返回的复盘报告结构不合法，请稍后重试") from exc
        except Exception as exc:
            raise AiServiceError(f"AI 复盘报告生成失败：{exc}") from exc

        report = ReviewReport(
            score=score,
            accuracy=accuracy,
            summary=draft.summary,
            weakPoints=draft.weakPoints,
            wrongQuestions=self._build_wrong_question_reviews(request),
            suggestions=draft.suggestions,
        )
        return GenerateReportResponse(report=report)

    @staticmethod
    def _build_wrong_question_reviews(request: GenerateReportRequest) -> list[WrongQuestionReview]:
        answer_by_question = {answer.questionId: answer for answer in request.answers}
        wrong_reviews: list[WrongQuestionReview] = []

        for question in request.questions:
            answer = answer_by_question.get(question.id)
            if not answer or answer.isCorrect:
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
