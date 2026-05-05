from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .errors import ApiHttpError
from .models import LearningRecord, User, now_utc
from .prompts import QUIZ_PROMPT_VERSION, REPORT_PROMPT_VERSION
from .schemas import (
    HistoryRecordDetail,
    HistoryRecordSummary,
    HistorySaveRequest,
)


def upsert_wechat_user(db: Session, openid: str, unionid: str | None) -> User:
    user = db.scalar(select(User).where(User.openid == openid))
    if user:
        user.unionid = unionid or user.unionid
        user.last_seen_at = now_utc()
    else:
        user = User(openid=openid, unionid=unionid)
        db.add(user)

    db.commit()
    db.refresh(user)
    return user


def save_learning_record(
    db: Session,
    user_id: str,
    payload: HistorySaveRequest,
) -> LearningRecord:
    score, total, accuracy = calculate_score(payload)
    record = db.scalar(
        select(LearningRecord).where(
            LearningRecord.user_id == user_id,
            LearningRecord.session_id == payload.sessionId,
        )
    )

    if not record:
        record = LearningRecord(user_id=user_id, session_id=payload.sessionId)
        db.add(record)

    model_name = get_settings().openai_model
    record.topic = payload.topic
    record.questions_json = [question.model_dump() for question in payload.questions]
    record.answers_json = [answer.model_dump() for answer in payload.answers]
    record.report_json = payload.report.model_dump()
    record.score = score
    record.total = total
    record.accuracy_percent = accuracy
    record.quiz_prompt_version = payload.quizPromptVersion or QUIZ_PROMPT_VERSION
    record.quiz_model_name = payload.quizModelName or model_name
    record.report_prompt_version = payload.reportPromptVersion or REPORT_PROMPT_VERSION
    record.report_model_name = payload.reportModelName or model_name
    record.completed_at = now_utc()

    db.commit()
    db.refresh(record)
    return record


def list_learning_records(db: Session, user_id: str) -> list[HistoryRecordSummary]:
    records = db.scalars(
        select(LearningRecord)
        .where(LearningRecord.user_id == user_id)
        .order_by(LearningRecord.completed_at.desc())
        .limit(50)
    ).all()
    return [to_summary(record) for record in records]


def get_learning_record(db: Session, user_id: str, record_id: str) -> HistoryRecordDetail:
    record = db.get(LearningRecord, record_id)
    if not record or record.user_id != user_id:
        raise ApiHttpError(404, "history_not_found", "学习记录不存在")
    return to_detail(record)


def calculate_score(payload: HistorySaveRequest) -> tuple[int, int, int]:
    question_by_id = {question.id: question for question in payload.questions}
    total = len(payload.questions)
    correct_count = sum(
        1
        for answer in payload.answers
        if answer.questionId in question_by_id
        and answer.selectedIndex == question_by_id[answer.questionId].answerIndex
    )
    accuracy = round(correct_count / total * 100) if total else 0
    return accuracy, total, accuracy


def to_summary(record: LearningRecord) -> HistoryRecordSummary:
    return HistoryRecordSummary(
        id=record.id,
        sessionId=record.session_id,
        topic=record.topic,
        score=record.score,
        total=record.total,
        accuracy=record.accuracy_percent,
        quizPromptVersion=record.quiz_prompt_version,
        quizModelName=record.quiz_model_name,
        reportPromptVersion=record.report_prompt_version,
        reportModelName=record.report_model_name,
        completedAt=ensure_datetime(record.completed_at),
        createdAt=ensure_datetime(record.created_at),
    )


def to_detail(record: LearningRecord) -> HistoryRecordDetail:
    return HistoryRecordDetail(
        **to_summary(record).model_dump(),
        questions=record.questions_json,
        answers=record.answers_json,
        report=record.report_json,
    )


def ensure_datetime(value: datetime) -> datetime:
    return value
