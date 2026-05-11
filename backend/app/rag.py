from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from math import sqrt

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .embeddings import EmbeddingClient
from .models import KnowledgeChunk, KnowledgeCollection, QuestionBankItem
from .quiz_answers import format_option_indexes
from .schemas import QuizQuestion


KEYWORD_RETRIEVAL_VERSION = "curated-rag-v1"
RETRIEVAL_VERSION = "hybrid-rag-v1"
VECTOR_CANDIDATE_LIMIT = 20
KEYWORD_CANDIDATE_LIMIT = 20


@dataclass
class RetrievedContext:
    question_items: list[QuestionBankItem] = field(default_factory=list)
    chunks: list[KnowledgeChunk] = field(default_factory=list)
    retrieval_version: str = RETRIEVAL_VERSION

    @property
    def has_context(self) -> bool:
        return bool(self.question_items or self.chunks)

    def source_ids(self) -> list[str]:
        ids = [item.id for item in self.question_items]
        ids.extend(chunk.id for chunk in self.chunks)
        return ids[:10]

    def to_prompt_context(self, *, max_chunks: int = 5) -> str:
        parts: list[str] = []
        for item in self.question_items[:5]:
            parts.append(
                "\n".join(
                    [
                        f"Question: {item.stem}",
                        f"Answer: {format_option_indexes(_options(item), _answer_indexes(item))}",
                        f"Explanation: {item.explanation}",
                        f"Knowledge point: {item.knowledge_point}",
                    ]
                )
            )
        for chunk in self.chunks[:max_chunks]:
            parts.append(
                "\n".join(
                    [
                        f"Title: {chunk.title}",
                        f"Content: {chunk.content}",
                        f"Source: {chunk.source_ref}",
                    ]
                )
            )
        return "\n\n---\n\n".join(parts)


@dataclass
class RetrievalDebugMatch:
    kind: str
    id: str
    collection_id: str
    collection_title: str
    title: str
    keyword_score: float
    vector_score: float
    total_score: float
    tags: list[str]
    source_ref: str = ""

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "id": self.id,
            "collectionId": self.collection_id,
            "collectionTitle": self.collection_title,
            "title": self.title,
            "keywordScore": round(self.keyword_score, 4),
            "vectorScore": round(self.vector_score, 4),
            "totalScore": round(self.total_score, 4),
            "tags": self.tags,
            "sourceRef": self.source_ref,
        }


@dataclass
class RetrievalDebugResult:
    query: str
    retrieval_version: str
    questions: list[RetrievalDebugMatch]
    chunks: list[RetrievalDebugMatch]

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "retrievalVersion": self.retrieval_version,
            "questions": [item.to_dict() for item in self.questions],
            "chunks": [item.to_dict() for item in self.chunks],
        }


def retrieve_curated_context(db: Session, query: str) -> RetrievedContext:
    embedding_client = EmbeddingClient(get_settings())
    return retrieve_curated_context_with_client(db, query, embedding_client=embedding_client)


def retrieve_curated_context_with_client(
    db: Session,
    query: str,
    *,
    embedding_client: EmbeddingClient,
) -> RetrievedContext:
    terms = _search_terms(query)
    if not terms:
        return RetrievedContext()

    question_items = _active_questions(db, limit=300)
    chunks = _active_chunks(db, limit=300)

    scored_questions = [
        (score, item)
        for item in question_items
        if (score := _score_question_item(item, terms, query)) > 0
    ]
    scored_chunks = [
        (score, chunk)
        for chunk in chunks
        if (score := _score_chunk(chunk, terms, query)) > 0
    ]

    scored_questions.sort(key=lambda value: value[0], reverse=True)
    scored_chunks.sort(key=lambda value: value[0], reverse=True)
    retrieval_version = KEYWORD_RETRIEVAL_VERSION

    if embedding_client.is_enabled:
        try:
            query_embedding = embedding_client.embed_query(query)
            vector_questions = _vector_question_scores(db, question_items, query_embedding)
            vector_chunks = _vector_chunk_scores(db, chunks, query_embedding)
        except Exception:
            vector_questions = []
            vector_chunks = []
        if vector_questions or vector_chunks:
            scored_questions = _merge_scores(
                scored_questions[:KEYWORD_CANDIDATE_LIMIT],
                vector_questions,
            )
            scored_chunks = _merge_scores(
                scored_chunks[:KEYWORD_CANDIDATE_LIMIT],
                vector_chunks,
            )
            retrieval_version = RETRIEVAL_VERSION

    return RetrievedContext(
        question_items=[item for _, item in scored_questions[:5]],
        chunks=[chunk for _, chunk in scored_chunks[:5]],
        retrieval_version=retrieval_version,
    )


def debug_retrieve_curated_context(
    db: Session,
    query: str,
    *,
    embedding_client: EmbeddingClient | None = None,
    limit: int = 5,
) -> RetrievalDebugResult:
    embedding_client = embedding_client or EmbeddingClient(get_settings())
    terms = _search_terms(query)
    if not terms:
        return RetrievalDebugResult(query=query, retrieval_version=KEYWORD_RETRIEVAL_VERSION, questions=[], chunks=[])

    question_items = _active_questions(db, limit=300)
    chunks = _active_chunks(db, limit=300)
    question_keyword_scores = {
        str(item.id): float(score)
        for item in question_items
        if (score := _score_question_item(item, terms, query)) > 0
    }
    chunk_keyword_scores = {
        str(chunk.id): float(score)
        for chunk in chunks
        if (score := _score_chunk(chunk, terms, query)) > 0
    }
    question_vector_scores: dict[str, float] = {}
    chunk_vector_scores: dict[str, float] = {}
    retrieval_version = KEYWORD_RETRIEVAL_VERSION

    if embedding_client.is_enabled:
        try:
            query_embedding = embedding_client.embed_query(query)
            question_vector_scores = {
                str(item.id): float(score)
                for score, item in _vector_question_scores(db, question_items, query_embedding)
            }
            chunk_vector_scores = {
                str(chunk.id): float(score)
                for score, chunk in _vector_chunk_scores(db, chunks, query_embedding)
            }
        except Exception:
            question_vector_scores = {}
            chunk_vector_scores = {}
        if question_vector_scores or chunk_vector_scores:
            retrieval_version = RETRIEVAL_VERSION

    return RetrievalDebugResult(
        query=query,
        retrieval_version=retrieval_version,
        questions=_debug_question_matches(
            question_items,
            question_keyword_scores,
            question_vector_scores,
            limit=limit,
        ),
        chunks=_debug_chunk_matches(
            chunks,
            chunk_keyword_scores,
            chunk_vector_scores,
            limit=limit,
        ),
    )


def question_bank_item_to_quiz_question(
    item: QuestionBankItem,
    *,
    question_id: str,
    retrieval_version: str = RETRIEVAL_VERSION,
) -> QuizQuestion:
    return QuizQuestion(
        id=question_id,
        stem=item.stem,
        options=_options(item),
        answerIndex=_answer_indexes(item)[0],
        answerIndexes=_answer_indexes(item),
        questionType=item.question_type,
        explanation=item.explanation,
        knowledgePoint=item.knowledge_point,
        sourceType="curated_question",
        sourceIds=[item.id, item.collection_id],
        retrievalVersion=retrieval_version,
    )


def tag_ai_question(
    question: QuizQuestion,
    *,
    question_id: str,
    source_type: str,
    source_ids: list[str] | None = None,
    retrieval_version: str | None = None,
) -> QuizQuestion:
    return question.model_copy(
        update={
            "id": question_id,
            "sourceType": source_type,
            "sourceIds": source_ids or [],
            "retrievalVersion": retrieval_version,
        }
    )


def _answer_indexes(item: QuestionBankItem) -> list[int]:
    indexes = item.answer_indexes_json or [item.answer_index]
    return sorted(dict.fromkeys(indexes))


def _options(item: QuestionBankItem) -> list[str]:
    return [str(option) for option in item.options_json]


def _search_terms(query: str) -> list[str]:
    normalized = query.strip().lower()
    terms = [normalized] if normalized else []
    terms.extend(re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]{2,}", normalized))
    return list(dict.fromkeys(term for term in terms if term))


def _active_questions(db: Session, *, limit: int) -> list[QuestionBankItem]:
    return db.scalars(
        select(QuestionBankItem)
        .join(QuestionBankItem.collection)
        .where(
            QuestionBankItem.is_active.is_(True),
            KnowledgeCollection.is_active.is_(True),
        )
        .limit(limit)
    ).all()


def _active_chunks(db: Session, *, limit: int) -> list[KnowledgeChunk]:
    return db.scalars(
        select(KnowledgeChunk)
        .join(KnowledgeChunk.collection)
        .where(
            KnowledgeChunk.is_active.is_(True),
            KnowledgeCollection.is_active.is_(True),
        )
        .limit(limit)
    ).all()


def _vector_question_scores(
    db: Session,
    fallback_items: list[QuestionBankItem],
    query_embedding: list[float],
) -> list[tuple[float, QuestionBankItem]]:
    if _dialect_name(db) == "postgresql":
        distance = QuestionBankItem.embedding.cosine_distance(query_embedding).label("distance")
        rows = db.execute(
            select(QuestionBankItem, distance)
            .join(QuestionBankItem.collection)
            .where(
                QuestionBankItem.is_active.is_(True),
                QuestionBankItem.embedding.is_not(None),
                KnowledgeCollection.is_active.is_(True),
            )
            .order_by(distance)
            .limit(VECTOR_CANDIDATE_LIMIT)
        ).all()
        return [(_distance_to_score(row[1]), row[0]) for row in rows]
    return _python_vector_scores(fallback_items, query_embedding)


def _vector_chunk_scores(
    db: Session,
    fallback_items: list[KnowledgeChunk],
    query_embedding: list[float],
) -> list[tuple[float, KnowledgeChunk]]:
    if _dialect_name(db) == "postgresql":
        distance = KnowledgeChunk.embedding.cosine_distance(query_embedding).label("distance")
        rows = db.execute(
            select(KnowledgeChunk, distance)
            .join(KnowledgeChunk.collection)
            .where(
                KnowledgeChunk.is_active.is_(True),
                KnowledgeChunk.embedding.is_not(None),
                KnowledgeCollection.is_active.is_(True),
            )
            .order_by(distance)
            .limit(VECTOR_CANDIDATE_LIMIT)
        ).all()
        return [(_distance_to_score(row[1]), row[0]) for row in rows]
    return _python_vector_scores(fallback_items, query_embedding)


def _dialect_name(db: Session) -> str:
    return db.get_bind().dialect.name


def _distance_to_score(distance: float | None) -> float:
    if distance is None:
        return 0
    return max(0.0, 1.0 - float(distance)) * 20


def _python_vector_scores(items, query_embedding: list[float]) -> list[tuple[float, object]]:
    scored = [
        (similarity * 20, item)
        for item in items
        if (embedding := getattr(item, "embedding", None)) is not None
        and (similarity := _cosine_similarity(query_embedding, embedding)) > 0
    ]
    scored.sort(key=lambda value: value[0], reverse=True)
    return scored[:VECTOR_CANDIDATE_LIMIT]


def _cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    left_values = [float(value) for value in left]
    right_values = [float(value) for value in right]
    if len(left_values) != len(right_values):
        return 0
    numerator = sum(a * b for a, b in zip(left_values, right_values, strict=True))
    left_norm = sqrt(sum(value * value for value in left_values))
    right_norm = sqrt(sum(value * value for value in right_values))
    if not left_norm or not right_norm:
        return 0
    return numerator / (left_norm * right_norm)


def _merge_scores(primary, secondary):
    merged: dict[str, tuple[float, object]] = {}
    for score, item in primary:
        merged[str(item.id)] = (float(score), item)
    for score, item in secondary:
        existing_score, _ = merged.get(str(item.id), (0.0, item))
        merged[str(item.id)] = (existing_score + float(score), item)
    return sorted(merged.values(), key=lambda value: value[0], reverse=True)


def _debug_question_matches(
    items: list[QuestionBankItem],
    keyword_scores: dict[str, float],
    vector_scores: dict[str, float],
    *,
    limit: int,
) -> list[RetrievalDebugMatch]:
    matches = [
        RetrievalDebugMatch(
            kind="question",
            id=str(item.id),
            collection_id=str(item.collection_id),
            collection_title=getattr(item.collection, "title", ""),
            title=item.stem,
            keyword_score=keyword_scores.get(str(item.id), 0.0),
            vector_score=vector_scores.get(str(item.id), 0.0),
            total_score=keyword_scores.get(str(item.id), 0.0) + vector_scores.get(str(item.id), 0.0),
            tags=item.tags_json or [],
        )
        for item in items
        if keyword_scores.get(str(item.id), 0.0) or vector_scores.get(str(item.id), 0.0)
    ]
    return sorted(matches, key=lambda value: value.total_score, reverse=True)[:limit]


def _debug_chunk_matches(
    items: list[KnowledgeChunk],
    keyword_scores: dict[str, float],
    vector_scores: dict[str, float],
    *,
    limit: int,
) -> list[RetrievalDebugMatch]:
    matches = [
        RetrievalDebugMatch(
            kind="chunk",
            id=str(chunk.id),
            collection_id=str(chunk.collection_id),
            collection_title=getattr(chunk.collection, "title", ""),
            title=chunk.title,
            keyword_score=keyword_scores.get(str(chunk.id), 0.0),
            vector_score=vector_scores.get(str(chunk.id), 0.0),
            total_score=keyword_scores.get(str(chunk.id), 0.0) + vector_scores.get(str(chunk.id), 0.0),
            tags=chunk.tags_json or [],
            source_ref=chunk.source_ref,
        )
        for chunk in items
        if keyword_scores.get(str(chunk.id), 0.0) or vector_scores.get(str(chunk.id), 0.0)
    ]
    return sorted(matches, key=lambda value: value.total_score, reverse=True)[:limit]


def _score_question_item(item: QuestionBankItem, terms: list[str], query: str) -> int:
    text = " ".join(
        [
            item.stem,
            item.explanation,
            item.knowledge_point,
            item.difficulty,
            " ".join(item.options_json),
            " ".join(item.tags_json or []),
            getattr(item.collection, "title", ""),
            getattr(item.collection, "description", ""),
            " ".join(getattr(item.collection, "tags_json", []) or []),
        ]
    )
    return _score_text(text, terms, query)


def _score_chunk(chunk: KnowledgeChunk, terms: list[str], query: str) -> int:
    text = " ".join(
        [
            chunk.title,
            chunk.content,
            chunk.source_ref,
            " ".join(chunk.tags_json or []),
            getattr(chunk.collection, "title", ""),
            getattr(chunk.collection, "description", ""),
            " ".join(getattr(chunk.collection, "tags_json", []) or []),
        ]
    )
    return _score_text(text, terms, query)


def _score_text(text: str, terms: list[str], query: str) -> int:
    target = text.lower()
    score = 0
    normalized_query = query.strip().lower()
    if normalized_query and normalized_query in target:
        score += 8
    for term in terms:
        if term in target:
            score += max(1, min(len(term), 6))
    return score
