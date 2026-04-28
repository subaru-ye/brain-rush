from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator


TextInput = Annotated[str, Field(min_length=2, max_length=4000)]


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
    options: list[str] = Field(min_length=3, max_length=4)
    answerIndex: int = Field(ge=0, le=3)
    explanation: str = Field(min_length=1, max_length=600)
    knowledgePoint: str = Field(min_length=1, max_length=80)

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


class GenerateQuizResponse(BaseModel):
    sessionId: str
    topic: str
    questions: list[QuizQuestion] = Field(min_length=5, max_length=5)


class UserAnswer(BaseModel):
    questionId: str = Field(min_length=1)
    selectedIndex: int = Field(ge=0, le=3)
    isCorrect: bool
    elapsedMs: int | None = Field(default=None, ge=0)


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
