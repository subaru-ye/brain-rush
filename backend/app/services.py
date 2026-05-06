from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session

from .llm import AiClientError, AiQuizDraft, AiReportDraft
from .prompts import QUIZ_PROMPT_VERSION, REPORT_PROMPT_VERSION
from .quiz_answers import format_option_indexes, is_answer_correct
from .rag import (
    RetrievedContext,
    question_bank_item_to_quiz_question,
    retrieve_curated_context,
    tag_ai_question,
)
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
    def generate_quiz(
        self,
        input_text: str,
        *,
        retrieved_context: str | None = None,
        question_count: int = 5,
    ) -> AiQuizDraft:
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
    db: Session | None = None

    def generate_quiz(self, input_text: str) -> GenerateQuizResponse:
        try:
            retrieved = retrieve_curated_context(self.db, input_text) if self.db else RetrievedContext()
            curated_questions = self._build_curated_questions(retrieved)
            missing_count = 5 - len(curated_questions)
            ai_questions: list[QuizQuestion] = []
            draft_topic = input_text.strip()

            if missing_count > 0:
                draft = self.ai_client.generate_quiz(
                    input_text,
                    retrieved_context=retrieved.to_prompt_context() if retrieved.has_context else None,
                    question_count=missing_count,
                )
                draft_topic = draft.topic.strip()
                if len(draft.questions) < missing_count:
                    raise ValueError("AI returned fewer questions than requested")
                ai_questions = self._tag_ai_questions(
                    questions=draft.questions[:missing_count],
                    start_index=len(curated_questions) + 1,
                    retrieved=retrieved,
                )

            questions = curated_questions + ai_questions
            return GenerateQuizResponse(
                sessionId=uuid4().hex,
                topic=input_text.strip() if curated_questions else draft_topic,
                questions=questions,
                quizPromptVersion=getattr(self.ai_client, "quiz_prompt_version", QUIZ_PROMPT_VERSION),
                quizModelName=getattr(self.ai_client, "model_name", ""),
                retrievalVersion=retrieved.retrieval_version if retrieved.has_context else None,
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
        return is_answer_correct(question, answer)

    @staticmethod
    def _build_curated_questions(retrieved: RetrievedContext) -> list[QuizQuestion]:
        return [
            question_bank_item_to_quiz_question(
                item,
                question_id=f"q{index}",
                retrieval_version=retrieved.retrieval_version,
            )
            for index, item in enumerate(retrieved.question_items[:5], start=1)
        ]

    @staticmethod
    def _tag_ai_questions(
        *,
        questions: list[QuizQuestion],
        start_index: int,
        retrieved: RetrievedContext,
    ) -> list[QuizQuestion]:
        source_type = "rag_generated" if retrieved.has_context else "ai_generated"
        source_ids = retrieved.source_ids() if retrieved.has_context else []
        retrieval_version = retrieved.retrieval_version if retrieved.has_context else None
        return [
            tag_ai_question(
                question,
                question_id=f"q{start_index + offset}",
                source_type=source_type,
                source_ids=source_ids,
                retrieval_version=retrieval_version,
            )
            for offset, question in enumerate(questions)
        ]

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
            selected = format_option_indexes(question.options, answer.selectedIndexes)
            correct = format_option_indexes(question.options, question.answerIndexes)
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
