from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import KnowledgeChunk, KnowledgeCollection, QuestionBankItem
from .schemas import QuizQuestion


def import_curated_file(path: str | Path) -> int:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    with SessionLocal() as db:
        return import_curated_payload(db, payload)


def import_curated_payload(db: Session, payload: dict[str, Any] | list[dict[str, Any]]) -> int:
    collections = payload.get("collections", []) if isinstance(payload, dict) else payload
    imported_count = 0
    for item in collections:
        collection = upsert_collection(db, item)
        imported_count += upsert_chunks(db, collection, item.get("chunks", []))
        imported_count += upsert_questions(db, collection, item.get("questions", []))

    db.commit()
    return imported_count


def upsert_collection(db: Session, payload: dict[str, Any]) -> KnowledgeCollection:
    title = str(payload["title"]).strip()
    collection = db.scalar(
        select(KnowledgeCollection).where(
            KnowledgeCollection.title == title,
            KnowledgeCollection.source_type == "curated",
        )
    )
    if not collection:
        collection = KnowledgeCollection(title=title, source_type="curated")
        db.add(collection)

    collection.description = str(payload.get("description", "")).strip()
    collection.tags_json = normalize_tags(payload.get("tags", []))
    collection.is_active = bool(payload.get("isActive", True))
    db.flush()
    return collection


def upsert_chunks(
    db: Session,
    collection: KnowledgeCollection,
    chunks: list[dict[str, Any]],
) -> int:
    count = 0
    for payload in chunks:
        title = str(payload["title"]).strip()
        chunk = db.scalar(
            select(KnowledgeChunk).where(
                KnowledgeChunk.collection_id == collection.id,
                KnowledgeChunk.title == title,
            )
        )
        if not chunk:
            chunk = KnowledgeChunk(collection_id=collection.id, title=title)
            db.add(chunk)
        chunk.content = str(payload["content"]).strip()
        chunk.source_ref = str(payload.get("sourceRef", "")).strip()
        chunk.tags_json = normalize_tags(payload.get("tags", []))
        chunk.is_active = bool(payload.get("isActive", True))
        count += 1
    return count


def upsert_questions(
    db: Session,
    collection: KnowledgeCollection,
    questions: list[dict[str, Any]],
) -> int:
    count = 0
    for payload in questions:
        quiz_question = QuizQuestion.model_validate(
            {
                "id": "q1",
                "stem": payload["stem"],
                "options": payload["options"],
                "answerIndex": payload.get("answerIndex"),
                "answerIndexes": payload.get("answerIndexes", []),
                "questionType": payload.get("questionType"),
                "explanation": payload["explanation"],
                "knowledgePoint": payload["knowledgePoint"],
            }
        )
        question = db.scalar(
            select(QuestionBankItem).where(
                QuestionBankItem.collection_id == collection.id,
                QuestionBankItem.stem == quiz_question.stem,
            )
        )
        if not question:
            question = QuestionBankItem(collection_id=collection.id, stem=quiz_question.stem)
            db.add(question)
        question.options_json = quiz_question.options
        question.answer_index = quiz_question.answerIndex
        question.answer_indexes_json = quiz_question.answerIndexes
        question.question_type = quiz_question.questionType or "single_choice"
        question.explanation = quiz_question.explanation
        question.knowledge_point = quiz_question.knowledgePoint
        question.difficulty = str(payload.get("difficulty", "normal")).strip() or "normal"
        question.tags_json = normalize_tags(payload.get("tags", []))
        question.is_active = bool(payload.get("isActive", True))
        count += 1
    return count


def normalize_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
