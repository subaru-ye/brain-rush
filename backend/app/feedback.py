from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import LearningRecord, QuestionFeedback, now_utc
from .quiz_answers import (
    format_option_indexes,
    get_answer_indexes,
    get_selected_indexes,
    is_answer_correct,
    normalize_question_dump,
)
from .schemas import (
    QuestionFeedbackRequest,
    QuestionFeedbackResponse,
    WrongQuestionItem,
)


def save_question_feedback(
    db: Session,
    user_id: str,
    payload: QuestionFeedbackRequest,
) -> QuestionFeedbackResponse:
    feedback = db.scalar(
        select(QuestionFeedback).where(
            QuestionFeedback.user_id == user_id,
            QuestionFeedback.session_id == payload.sessionId,
            QuestionFeedback.question_id == payload.questionId,
            QuestionFeedback.reason == payload.reason,
        )
    )

    if not feedback:
        feedback = QuestionFeedback(
            user_id=user_id,
            session_id=payload.sessionId,
            question_id=payload.questionId,
            reason=payload.reason,
        )
        db.add(feedback)

    feedback.topic = payload.topic
    feedback.question_json = normalize_question_dump(payload.questionSnapshot)
    feedback.selected_index = payload.selectedIndex
    feedback.selected_indexes_json = payload.selectedIndexes or (
        [payload.selectedIndex] if payload.selectedIndex is not None else []
    )
    feedback.source_page = payload.sourcePage
    feedback.updated_at = now_utc()

    db.commit()
    db.refresh(feedback)
    return QuestionFeedbackResponse(
        id=feedback.id,
        createdAt=feedback.created_at,
        updatedAt=feedback.updated_at,
    )


def list_wrong_questions(
    db: Session,
    user_id: str,
    *,
    limit: int = 50,
) -> list[WrongQuestionItem]:
    records = db.scalars(
        select(LearningRecord)
        .where(LearningRecord.user_id == user_id)
        .order_by(LearningRecord.completed_at.desc())
        .limit(100)
    ).all()

    items: list[WrongQuestionItem] = []
    for record in records:
        question_by_id = {question.get("id"): question for question in record.questions_json}
        for answer in record.answers_json:
            question = question_by_id.get(answer.get("questionId"))
            if not question:
                continue

            selected_indexes = get_selected_indexes(answer)
            answer_indexes = get_answer_indexes(question)
            options = question.get("options") or []
            if (
                not selected_indexes
                or not answer_indexes
                or is_answer_correct(question, answer)
                or any(index >= len(options) for index in selected_indexes)
                or any(index >= len(options) for index in answer_indexes)
            ):
                continue

            items.append(
                WrongQuestionItem(
                    recordId=record.id,
                    sessionId=record.session_id,
                    topic=record.topic,
                    questionId=str(question.get("id", "")),
                    questionType=question.get("questionType"),
                    stem=str(question.get("stem", "")),
                    options=[str(option) for option in options],
                    answerIndex=answer_indexes[0],
                    answerIndexes=answer_indexes,
                    selectedIndex=selected_indexes[0],
                    selectedIndexes=selected_indexes,
                    explanation=str(question.get("explanation", "")),
                    knowledgePoint=str(question.get("knowledgePoint", "")),
                    userAnswer=format_option_indexes(options, selected_indexes),
                    correctAnswer=format_option_indexes(options, answer_indexes),
                    completedAt=record.completed_at,
                )
            )
            if len(items) >= limit:
                return items

    return items
