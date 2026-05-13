from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .prompts import QUIZ_PROMPT_VERSION, REPORT_PROMPT_VERSION


TextInput = Annotated[str, Field(min_length=2, max_length=4000)]
QuestionType = Literal["single_choice", "multiple_choice", "true_false"]


class GenerateQuizRequest(BaseModel):
    inputText: TextInput

    @field_validator("inputText")
    @classmethod
    def normalize_input(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("学习内容至少需要 2 个字符")
        return normalized


class QuizQuestion(BaseModel):
    id: str = Field(min_length=1)
    stem: str = Field(min_length=1, max_length=300)
    options: list[str] = Field(min_length=2, max_length=4)
    answerIndex: int = Field(ge=0, le=3)
    answerIndexes: list[int] = Field(default_factory=list, max_length=4)
    questionType: QuestionType | None = None
    explanation: str = Field(min_length=1, max_length=600)
    knowledgePoint: str = Field(min_length=1, max_length=80)
    sourceType: str | None = Field(default=None, max_length=40)
    sourceIds: list[str] = Field(default_factory=list, max_length=10)
    retrievalVersion: str | None = Field(default=None, max_length=40)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_answer_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        next_data = dict(data)
        answer_indexes = next_data.get("answerIndexes")
        answer_index = next_data.get("answerIndex")
        if not answer_indexes and answer_index is not None:
            answer_indexes = [answer_index]
            next_data["answerIndexes"] = answer_indexes
        if answer_index is None and isinstance(answer_indexes, list) and answer_indexes:
            next_data["answerIndex"] = answer_indexes[0]
        if not next_data.get("questionType") and isinstance(answer_indexes, list):
            next_data["questionType"] = (
                "multiple_choice" if len(answer_indexes) > 1 else "single_choice"
            )
        return next_data

    @field_validator("options")
    @classmethod
    def validate_options(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("选项不能为空")
        return cleaned

    @model_validator(mode="after")
    def validate_answer_index(self) -> "QuizQuestion":
        if self.answerIndex >= len(self.options):
            raise ValueError("正确答案下标必须指向已有选项")
        return self


    @model_validator(mode="after")
    def validate_question_type_answers(self) -> "QuizQuestion":
        answer_indexes = sorted(dict.fromkeys(self.answerIndexes))
        if not answer_indexes:
            answer_indexes = [self.answerIndex]
        if any(index < 0 or index >= len(self.options) for index in answer_indexes):
            raise ValueError("answerIndexes must point to existing options")

        question_type = self.questionType or (
            "multiple_choice" if len(answer_indexes) > 1 else "single_choice"
        )
        if question_type == "multiple_choice" and len(answer_indexes) < 2:
            raise ValueError("multiple_choice requires at least two correct answers")
        if question_type in {"single_choice", "true_false"} and len(answer_indexes) != 1:
            raise ValueError("single_choice and true_false require one correct answer")
        if question_type == "true_false" and len(self.options) != 2:
            raise ValueError("true_false requires exactly two options")

        self.questionType = question_type
        self.answerIndexes = answer_indexes
        self.answerIndex = answer_indexes[0]
        return self


class GenerateQuizResponse(BaseModel):
    sessionId: str
    topic: str
    questions: list[QuizQuestion] = Field(min_length=5, max_length=5)
    quizPromptVersion: str = Field(default=QUIZ_PROMPT_VERSION, max_length=40)
    quizModelName: str = Field(default="", max_length=120)
    retrievalVersion: str | None = Field(default=None, max_length=40)


class UserAnswer(BaseModel):
    questionId: str = Field(min_length=1)
    selectedIndex: int = Field(ge=0, le=3)
    selectedIndexes: list[int] = Field(default_factory=list, max_length=4)
    isCorrect: bool
    elapsedMs: int | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_selected_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        next_data = dict(data)
        selected_indexes = next_data.get("selectedIndexes")
        selected_index = next_data.get("selectedIndex")
        if not selected_indexes and selected_index is not None:
            selected_indexes = [selected_index]
            next_data["selectedIndexes"] = selected_indexes
        if selected_index is None and isinstance(selected_indexes, list) and selected_indexes:
            next_data["selectedIndex"] = selected_indexes[0]
        return next_data

    @model_validator(mode="after")
    def validate_selected_indexes(self) -> "UserAnswer":
        selected_indexes = sorted(dict.fromkeys(self.selectedIndexes))
        if not selected_indexes:
            selected_indexes = [self.selectedIndex]
        if any(index < 0 or index > 3 for index in selected_indexes):
            raise ValueError("selectedIndexes must be between 0 and 3")
        self.selectedIndexes = selected_indexes
        self.selectedIndex = selected_indexes[0]
        return self


class GenerateReportRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=120)
    questions: list[QuizQuestion] = Field(min_length=1, max_length=20)
    answers: list[UserAnswer] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_answer_references(self) -> "GenerateReportRequest":
        question_ids = {question.id for question in self.questions}
        answer_ids = {answer.questionId for answer in self.answers}
        if not answer_ids.issubset(question_ids):
            raise ValueError("答案中包含不存在的题目 ID")
        return self


class WrongQuestionReview(BaseModel):
    questionId: str
    stem: str
    userAnswer: str
    correctAnswer: str
    explanation: str
    knowledgePoint: str


class ReviewReport(BaseModel):
    score: int = Field(ge=0, le=100)
    accuracy: int = Field(ge=0, le=100)
    summary: str = Field(min_length=1, max_length=800)
    weakPoints: list[str] = Field(default_factory=list, max_length=5)
    wrongQuestions: list[WrongQuestionReview] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list, max_length=5)


class GenerateReportResponse(BaseModel):
    report: ReviewReport
    reportPromptVersion: str = Field(default=REPORT_PROMPT_VERSION, max_length=40)
    reportModelName: str = Field(default="", max_length=120)


class AiGenerationError(BaseModel):
    code: str
    detail: str


class ApiError(BaseModel):
    code: str
    detail: str


class WechatLoginRequest(BaseModel):
    code: str = Field(min_length=1)


class AuthResponse(BaseModel):
    token: str
    userId: str


class HistorySaveRequest(BaseModel):
    sessionId: str = Field(min_length=1)
    topic: str = Field(min_length=1, max_length=120)
    questions: list[QuizQuestion] = Field(min_length=1, max_length=20)
    answers: list[UserAnswer] = Field(min_length=1, max_length=20)
    report: ReviewReport
    quizPromptVersion: str | None = Field(default=None, max_length=40)
    quizModelName: str | None = Field(default=None, max_length=120)
    reportPromptVersion: str | None = Field(default=None, max_length=40)
    reportModelName: str | None = Field(default=None, max_length=120)
    retrievalVersion: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def validate_answer_references(self) -> "HistorySaveRequest":
        question_ids = {question.id for question in self.questions}
        answer_ids = {answer.questionId for answer in self.answers}
        if not answer_ids.issubset(question_ids):
            raise ValueError("绛旀涓寘鍚笉瀛樺湪鐨勯鐩?ID")
        return self


class HistoryRecordSummary(BaseModel):
    id: str
    sessionId: str
    topic: str
    score: int
    total: int
    accuracy: int
    quizPromptVersion: str | None = None
    quizModelName: str | None = None
    reportPromptVersion: str | None = None
    reportModelName: str | None = None
    retrievalVersion: str | None = None
    completedAt: datetime
    createdAt: datetime


class HistoryRecordDetail(HistoryRecordSummary):
    questions: list[QuizQuestion]
    answers: list[UserAnswer]
    report: ReviewReport


class HistorySaveResponse(BaseModel):
    record: HistoryRecordDetail


class HistoryListResponse(BaseModel):
    records: list[HistoryRecordSummary]


QuestionFeedbackReason = Literal["question_inaccurate", "explanation_unclear", "irrelevant"]
QuestionFeedbackSource = Literal["quiz", "report"]


class QuestionFeedbackRequest(BaseModel):
    sessionId: str = Field(min_length=1, max_length=64)
    topic: str = Field(min_length=1, max_length=120)
    questionId: str = Field(min_length=1, max_length=128)
    reason: QuestionFeedbackReason
    questionSnapshot: QuizQuestion
    selectedIndex: int | None = Field(default=None, ge=0, le=3)
    selectedIndexes: list[int] = Field(default_factory=list, max_length=4)
    sourcePage: QuestionFeedbackSource


class QuestionFeedbackResponse(BaseModel):
    id: str
    createdAt: datetime
    updatedAt: datetime


class WrongQuestionItem(BaseModel):
    recordId: str
    sessionId: str
    topic: str
    questionId: str
    questionType: QuestionType | None = None
    stem: str
    options: list[str]
    answerIndex: int | None = None
    answerIndexes: list[int] = Field(default_factory=list)
    selectedIndex: int | None = None
    selectedIndexes: list[int] = Field(default_factory=list)
    explanation: str
    knowledgePoint: str
    userAnswer: str
    correctAnswer: str
    completedAt: datetime


class WrongQuestionListResponse(BaseModel):
    items: list[WrongQuestionItem]


class RagAdminCollectionItem(BaseModel):
    id: str
    title: str
    description: str
    sourceType: str
    tags: list[str]
    isActive: bool
    documentCount: int
    chunkCount: int
    questionCount: int
    createdAt: datetime
    updatedAt: datetime


class RagAdminCollectionListResponse(BaseModel):
    items: list[RagAdminCollectionItem]


class RagAdminCollectionUpdateRequest(BaseModel):
    description: str | None = Field(default=None, max_length=600)
    tags: list[str] | None = Field(default=None, max_length=20)
    isActive: bool | None = None


class RagAdminDocumentItem(BaseModel):
    id: str
    collectionId: str
    collectionTitle: str
    title: str
    sourceType: str
    sourceUri: str
    contentHash: str | None = None
    metadata: dict
    status: str
    isActive: bool
    chunkCount: int = 0
    createdAt: datetime
    updatedAt: datetime


class RagAdminDocumentListResponse(BaseModel):
    items: list[RagAdminDocumentItem]
    total: int
    limit: int
    offset: int


class RagAdminDocumentUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    sourceUri: str | None = Field(default=None, max_length=500)
    metadata: dict | None = None
    status: str | None = Field(default=None, min_length=1, max_length=32)
    isActive: bool | None = None


class RagAdminChunkItem(BaseModel):
    id: str
    collectionId: str
    collectionTitle: str
    documentId: str | None = None
    documentTitle: str | None = None
    title: str
    content: str
    sourceRef: str
    tags: list[str]
    isActive: bool
    embeddingModel: str | None = None
    embeddingVersion: str | None = None
    contentHash: str | None = None
    embeddedAt: datetime | None = None
    createdAt: datetime


class RagAdminChunkListResponse(BaseModel):
    items: list[RagAdminChunkItem]
    total: int
    limit: int
    offset: int


class RagAdminChunkUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    content: str | None = Field(default=None, min_length=1)
    sourceRef: str | None = Field(default=None, max_length=200)
    tags: list[str] | None = Field(default=None, max_length=20)
    isActive: bool | None = None


class RagAdminQuestionItem(BaseModel):
    id: str
    collectionId: str
    collectionTitle: str
    stem: str
    options: list[str]
    answerIndex: int
    answerIndexes: list[int]
    questionType: str
    explanation: str
    knowledgePoint: str
    difficulty: str
    tags: list[str]
    isActive: bool
    embeddingModel: str | None = None
    embeddingVersion: str | None = None
    contentHash: str | None = None
    embeddedAt: datetime | None = None
    createdAt: datetime
    updatedAt: datetime


class RagAdminQuestionListResponse(BaseModel):
    items: list[RagAdminQuestionItem]
    total: int
    limit: int
    offset: int


class RagAdminQuestionUpdateRequest(BaseModel):
    difficulty: str | None = Field(default=None, min_length=1, max_length=24)
    tags: list[str] | None = Field(default=None, max_length=20)
    isActive: bool | None = None


class RagAdminReembedResponse(BaseModel):
    id: str
    embeddingModel: str
    embeddingVersion: str
    contentHash: str
    embeddedAt: datetime
