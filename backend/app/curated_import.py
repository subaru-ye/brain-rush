from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import SessionLocal
from .embeddings import (
    EmbeddingClient,
    chunk_embedding_text,
    content_hash,
    question_embedding_text,
)
from .models import KnowledgeChunk, KnowledgeCollection, KnowledgeDocument, QuestionBankItem
from .models import now_utc
from .schemas import QuizQuestion


@dataclass
class ImportStats:
    total_imported: int = 0
    embeddings_generated: int = 0
    embeddings_skipped: int = 0
    embeddings_failed: int = 0


def import_curated_file(path: str | Path) -> int:
    return import_curated_file_with_stats(path).total_imported


def import_curated_file_with_stats(path: str | Path) -> ImportStats:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    with SessionLocal() as db:
        return import_curated_payload_with_stats(db, payload)


def import_curated_payload(db: Session, payload: dict[str, Any] | list[dict[str, Any]]) -> int:
    return import_curated_payload_with_stats(db, payload).total_imported


def import_curated_payload_with_stats(
    db: Session,
    payload: dict[str, Any] | list[dict[str, Any]],
    *,
    embedding_client: EmbeddingClient | None = None,
) -> ImportStats:
    collections = payload.get("collections", []) if isinstance(payload, dict) else payload
    stats = ImportStats()
    embedding_client = embedding_client or EmbeddingClient(get_settings())
    pending_embeddings: list[tuple[KnowledgeChunk | QuestionBankItem, str, str]] = []

    for item in collections:
        collection = upsert_collection(db, item)
        chunks = upsert_chunks(db, collection, item.get("chunks", []))
        for document_payload in item.get("documents", []):
            document = upsert_document(db, collection, document_payload)
            chunks.extend(
                upsert_chunks(
                    db,
                    collection,
                    document_payload.get("chunks", []),
                    document=document,
                )
            )
        questions = upsert_questions(db, collection, item.get("questions", []))
        stats.total_imported += len(chunks) + len(questions)
        pending_embeddings.extend(
            collect_embedding_targets(chunks, embedding_client, chunk_embedding_text, stats)
        )
        pending_embeddings.extend(
            collect_embedding_targets(questions, embedding_client, question_embedding_text, stats)
        )

    if pending_embeddings and embedding_client.is_enabled:
        try:
            embeddings = embedding_client.embed_texts([text for _, text, _ in pending_embeddings])
        except Exception:
            stats.embeddings_failed = len(pending_embeddings)
            db.rollback()
            raise
        for (item, _, digest), embedding in zip(pending_embeddings, embeddings, strict=True):
            item.embedding = embedding
            item.embedding_model = embedding_client.model_name
            item.embedding_version = embedding_client.version
            item.content_hash = digest
            item.embedded_at = now_utc()
            stats.embeddings_generated += 1

    db.commit()
    return stats


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


def upsert_document(
    db: Session,
    collection: KnowledgeCollection,
    payload: dict[str, Any],
) -> KnowledgeDocument:
    title = str(payload["title"]).strip()
    source_type = str(payload.get("sourceType", "manual")).strip() or "manual"
    source_uri = str(payload.get("sourceUri", "")).strip()
    if source_uri:
        lookup = (
            KnowledgeDocument.collection_id == collection.id,
            KnowledgeDocument.source_type == source_type,
            KnowledgeDocument.source_uri == source_uri,
        )
    else:
        lookup = (
            KnowledgeDocument.collection_id == collection.id,
            KnowledgeDocument.source_type == source_type,
            KnowledgeDocument.title == title,
        )
    document = db.scalar(select(KnowledgeDocument).where(*lookup))
    if not document:
        document = KnowledgeDocument(
            collection_id=collection.id,
            title=title,
            source_type=source_type,
            source_uri=source_uri,
        )
        db.add(document)

    metadata = payload.get("metadata", {})
    document.title = title
    document.source_type = source_type
    document.source_uri = source_uri
    document.content_hash = str(payload.get("contentHash", "")).strip() or None
    document.metadata_json = metadata if isinstance(metadata, dict) else {}
    document.status = str(payload.get("status", "active")).strip() or "active"
    document.is_active = bool(payload.get("isActive", True))
    db.flush()
    return document


def upsert_chunks(
    db: Session,
    collection: KnowledgeCollection,
    chunks: list[dict[str, Any]],
    *,
    document: KnowledgeDocument | None = None,
) -> list[KnowledgeChunk]:
    items: list[KnowledgeChunk] = []
    for payload in chunks:
        title = str(payload["title"]).strip()
        if document:
            chunk = db.scalar(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.collection_id == collection.id,
                    KnowledgeChunk.document_id == document.id,
                    KnowledgeChunk.title == title,
                )
            )
            if not chunk:
                chunk = db.scalar(
                    select(KnowledgeChunk).where(
                        KnowledgeChunk.collection_id == collection.id,
                        KnowledgeChunk.document_id.is_(None),
                        KnowledgeChunk.title == title,
                    )
                )
        else:
            chunk = db.scalar(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.collection_id == collection.id,
                    KnowledgeChunk.document_id.is_(None),
                    KnowledgeChunk.title == title,
                )
            )
        if not chunk:
            chunk = KnowledgeChunk(collection_id=collection.id, title=title)
            db.add(chunk)
        source_ref = str(payload.get("sourceRef", "")).strip()
        if document and not source_ref:
            source_ref = document.source_uri or document.title
        chunk.document_id = document.id if document else None
        chunk.document = document
        chunk.title = title
        chunk.content = str(payload["content"]).strip()
        chunk.source_ref = source_ref
        chunk.tags_json = normalize_tags(payload.get("tags", []))
        chunk.is_active = bool(payload.get("isActive", True))
        items.append(chunk)
    db.flush()
    return items

def upsert_questions(
    db: Session,
    collection: KnowledgeCollection,
    questions: list[dict[str, Any]],
) -> list[QuestionBankItem]:
    items: list[QuestionBankItem] = []
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
        items.append(question)
    db.flush()
    return items


def collect_embedding_targets(
    items: list[KnowledgeChunk | QuestionBankItem],
    embedding_client: EmbeddingClient,
    text_builder: Callable[[Any], str],
    stats: ImportStats,
) -> list[tuple[KnowledgeChunk | QuestionBankItem, str, str]]:
    targets: list[tuple[KnowledgeChunk | QuestionBankItem, str, str]] = []
    for item in items:
        text = text_builder(item)
        digest = content_hash(text)
        if not embedding_client.is_enabled:
            item.content_hash = digest
            stats.embeddings_skipped += 1
            continue
        if (
            item.embedding is not None
            and item.content_hash == digest
            and item.embedding_model == embedding_client.model_name
            and item.embedding_version == embedding_client.version
        ):
            stats.embeddings_skipped += 1
            continue
        targets.append((item, text, digest))
    return targets


def normalize_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
