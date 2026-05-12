from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from math import sqrt

from sqlalchemy import text
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .embeddings import EmbeddingClient
from .models import KnowledgeChunk, KnowledgeCollection, QuestionBankItem
from .quiz_answers import format_option_indexes
from .schemas import QuizQuestion


KEYWORD_RETRIEVAL_VERSION = "hybrid-rag-v1.2"
RETRIEVAL_VERSION = "hybrid-rag-v1.2"
VECTOR_CANDIDATE_LIMIT = 20
KEYWORD_CANDIDATE_LIMIT = 20
FUSION_METHOD = "rrf"
RRF_K = 60
RRF_KEYWORD_WEIGHT = 1.0
RRF_VECTOR_WEIGHT = 1.0
KEYWORD_DEBUG_KEYS = ("title", "tags", "body", "source", "collection")
PYTHON_FIELD_WEIGHTS = {
    "title": 18.0,
    "tags": 16.0,
    "body": 8.0,
    "source": 3.0,
    "collection": 5.0,
}
FTS_FIELD_WEIGHTS = {
    "title": 24.0,
    "tags": 20.0,
    "body": 10.0,
    "source": 4.0,
    "collection": 6.0,
}


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
    keyword_score_breakdown: dict[str, float] = field(default_factory=dict)
    keyword_rank: int | None = None
    vector_rank: int | None = None
    fusion_method: str = FUSION_METHOD

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
            "keywordRank": self.keyword_rank,
            "vectorRank": self.vector_rank,
            "fusionMethod": self.fusion_method,
            "keywordScoreBreakdown": {
                key: round(self.keyword_score_breakdown.get(key, 0.0), 4)
                for key in KEYWORD_DEBUG_KEYS
            },
            "tags": self.tags,
            "sourceRef": self.source_ref,
        }


@dataclass
class KeywordMatch:
    score: float
    item: object
    breakdown: dict[str, float]


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

    question_keyword_matches = _keyword_question_matches(db, question_items, terms, query)
    chunk_keyword_matches = _keyword_chunk_matches(db, chunks, terms, query)
    scored_questions = [(match.score, match.item) for match in question_keyword_matches]
    scored_chunks = [(match.score, match.item) for match in chunk_keyword_matches]

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
            scored_questions = _merge_scores_rrf(
                scored_questions[:KEYWORD_CANDIDATE_LIMIT],
                vector_questions,
            )
            scored_chunks = _merge_scores_rrf(
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
    question_keyword_matches = _keyword_question_matches(db, question_items, terms, query)
    chunk_keyword_matches = _keyword_chunk_matches(db, chunks, terms, query)
    question_keyword_scores = {
        _id_key(match.item): float(match.score) for match in question_keyword_matches
    }
    chunk_keyword_scores = {
        _id_key(match.item): float(match.score) for match in chunk_keyword_matches
    }
    question_keyword_breakdowns = {
        _id_key(match.item): match.breakdown for match in question_keyword_matches
    }
    chunk_keyword_breakdowns = {
        _id_key(match.item): match.breakdown for match in chunk_keyword_matches
    }
    question_vector_scores: dict[str, float] = {}
    chunk_vector_scores: dict[str, float] = {}
    question_vector_matches: list[tuple[float, QuestionBankItem]] = []
    chunk_vector_matches: list[tuple[float, KnowledgeChunk]] = []
    retrieval_version = KEYWORD_RETRIEVAL_VERSION

    if embedding_client.is_enabled:
        try:
            query_embedding = embedding_client.embed_query(query)
            question_vector_matches = _vector_question_scores(db, question_items, query_embedding)
            chunk_vector_matches = _vector_chunk_scores(db, chunks, query_embedding)
            question_vector_scores = {
                str(item.id): float(score)
                for score, item in question_vector_matches
            }
            chunk_vector_scores = {
                str(chunk.id): float(score)
                for score, chunk in chunk_vector_matches
            }
        except Exception:
            question_vector_scores = {}
            chunk_vector_scores = {}
            question_vector_matches = []
            chunk_vector_matches = []
        if question_vector_scores or chunk_vector_scores:
            retrieval_version = RETRIEVAL_VERSION

    question_keyword_ranks = _score_rank_lookup(
        [(match.score, match.item) for match in question_keyword_matches[:KEYWORD_CANDIDATE_LIMIT]]
    )
    chunk_keyword_ranks = _score_rank_lookup(
        [(match.score, match.item) for match in chunk_keyword_matches[:KEYWORD_CANDIDATE_LIMIT]]
    )
    question_vector_ranks = _score_rank_lookup(question_vector_matches)
    chunk_vector_ranks = _score_rank_lookup(chunk_vector_matches)

    return RetrievalDebugResult(
        query=query,
        retrieval_version=retrieval_version,
        questions=_debug_question_matches(
            question_items,
            question_keyword_scores,
            question_vector_scores,
            question_keyword_breakdowns,
            question_keyword_ranks,
            question_vector_ranks,
            limit=limit,
        ),
        chunks=_debug_chunk_matches(
            chunks,
            chunk_keyword_scores,
            chunk_vector_scores,
            chunk_keyword_breakdowns,
            chunk_keyword_ranks,
            chunk_vector_ranks,
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


def _keyword_question_matches(
    db: Session,
    items: list[QuestionBankItem],
    terms: list[str],
    query: str,
) -> list[KeywordMatch]:
    python_matches = _python_keyword_question_matches(items, terms, query)
    if _dialect_name(db) != "postgresql":
        return python_matches
    try:
        fts_matches, config_name = _postgres_keyword_question_matches(db, items, query)
    except Exception:
        return python_matches
    if config_name == "jiebacfg" and fts_matches:
        return fts_matches
    return _merge_keyword_matches(fts_matches, python_matches)


def _keyword_chunk_matches(
    db: Session,
    items: list[KnowledgeChunk],
    terms: list[str],
    query: str,
) -> list[KeywordMatch]:
    python_matches = _python_keyword_chunk_matches(items, terms, query)
    if _dialect_name(db) != "postgresql":
        return python_matches
    try:
        fts_matches, config_name = _postgres_keyword_chunk_matches(db, items, query)
    except Exception:
        return python_matches
    if config_name == "jiebacfg" and fts_matches:
        return fts_matches
    return _merge_keyword_matches(fts_matches, python_matches)


def _python_keyword_question_matches(
    items: list[QuestionBankItem],
    terms: list[str],
    query: str,
) -> list[KeywordMatch]:
    matches = []
    for item in items:
        breakdown = _score_question_item(item, terms, query)
        score = sum(breakdown.values())
        if score > 0:
            matches.append(KeywordMatch(score=score, item=item, breakdown=breakdown))
    return sorted(matches, key=lambda value: value.score, reverse=True)


def _python_keyword_chunk_matches(
    items: list[KnowledgeChunk],
    terms: list[str],
    query: str,
) -> list[KeywordMatch]:
    matches = []
    for chunk in items:
        breakdown = _score_chunk(chunk, terms, query)
        score = sum(breakdown.values())
        if score > 0:
            matches.append(KeywordMatch(score=score, item=chunk, breakdown=breakdown))
    return sorted(matches, key=lambda value: value.score, reverse=True)


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


def _postgres_keyword_question_matches(
    db: Session,
    fallback_items: list[QuestionBankItem],
    query: str,
) -> tuple[list[KeywordMatch], str]:
    config_name = _postgres_fts_config_name(db)
    rows = db.execute(
        text(
            """
            with search_query as (
                select plainto_tsquery(cast(:config_name as regconfig), :query) as query_value
            )
            select
                replace(q.id::text, '-', '') as item_id,
                ts_rank_cd(to_tsvector(cast(:config_name as regconfig), coalesce(q.stem, '') || ' ' || coalesce(q.knowledge_point, '')), sq.query_value) as title_rank,
                ts_rank_cd(to_tsvector(cast(:config_name as regconfig), coalesce(q.tags_json::text, '')), sq.query_value) as tags_rank,
                ts_rank_cd(to_tsvector(cast(:config_name as regconfig), coalesce(q.options_json::text, '') || ' ' || coalesce(q.explanation, '') || ' ' || coalesce(q.difficulty, '')), sq.query_value) as body_rank,
                0.0 as source_rank,
                ts_rank_cd(to_tsvector(cast(:config_name as regconfig), concat_ws(' ', c.title, c.description, c.tags_json::text)), sq.query_value) as collection_rank
            from question_bank_items q
            join knowledge_collections c on c.id = q.collection_id
            cross join search_query sq
            where q.is_active is true
              and c.is_active is true
              and (
                (
                  setweight(to_tsvector(cast(:config_name as regconfig), coalesce(q.stem, '') || ' ' || coalesce(q.knowledge_point, '')), 'A') ||
                  setweight(to_tsvector(cast(:config_name as regconfig), coalesce(q.tags_json::text, '')), 'A') ||
                  setweight(to_tsvector(cast(:config_name as regconfig), coalesce(q.options_json::text, '') || ' ' || coalesce(q.explanation, '') || ' ' || coalesce(q.difficulty, '')), 'B')
                ) @@ sq.query_value
                or to_tsvector(cast(:config_name as regconfig), concat_ws(' ', c.title, c.description, c.tags_json::text)) @@ sq.query_value
              )
            order by title_rank desc, tags_rank desc, body_rank desc, collection_rank desc
            limit :limit
            """
        ),
        {
            "config_name": config_name,
            "query": query,
            "limit": KEYWORD_CANDIDATE_LIMIT,
        },
    ).mappings()
    return _keyword_matches_from_fts_rows(rows, fallback_items), config_name


def _postgres_keyword_chunk_matches(
    db: Session,
    fallback_items: list[KnowledgeChunk],
    query: str,
) -> tuple[list[KeywordMatch], str]:
    config_name = _postgres_fts_config_name(db)
    rows = db.execute(
        text(
            """
            with search_query as (
                select plainto_tsquery(cast(:config_name as regconfig), :query) as query_value
            )
            select
                replace(k.id::text, '-', '') as item_id,
                ts_rank_cd(to_tsvector(cast(:config_name as regconfig), coalesce(k.title, '')), sq.query_value) as title_rank,
                ts_rank_cd(to_tsvector(cast(:config_name as regconfig), coalesce(k.tags_json::text, '')), sq.query_value) as tags_rank,
                ts_rank_cd(to_tsvector(cast(:config_name as regconfig), coalesce(k.content, '')), sq.query_value) as body_rank,
                ts_rank_cd(to_tsvector(cast(:config_name as regconfig), coalesce(k.source_ref, '')), sq.query_value) as source_rank,
                ts_rank_cd(to_tsvector(cast(:config_name as regconfig), concat_ws(' ', c.title, c.description, c.tags_json::text)), sq.query_value) as collection_rank
            from knowledge_chunks k
            join knowledge_collections c on c.id = k.collection_id
            cross join search_query sq
            where k.is_active is true
              and c.is_active is true
              and (
                (
                  setweight(to_tsvector(cast(:config_name as regconfig), coalesce(k.title, '')), 'A') ||
                  setweight(to_tsvector(cast(:config_name as regconfig), coalesce(k.tags_json::text, '')), 'A') ||
                  setweight(to_tsvector(cast(:config_name as regconfig), coalesce(k.content, '')), 'B') ||
                  setweight(to_tsvector(cast(:config_name as regconfig), coalesce(k.source_ref, '')), 'D')
                ) @@ sq.query_value
                or to_tsvector(cast(:config_name as regconfig), concat_ws(' ', c.title, c.description, c.tags_json::text)) @@ sq.query_value
              )
            order by title_rank desc, tags_rank desc, body_rank desc, collection_rank desc, source_rank desc
            limit :limit
            """
        ),
        {
            "config_name": config_name,
            "query": query,
            "limit": KEYWORD_CANDIDATE_LIMIT,
        },
    ).mappings()
    return _keyword_matches_from_fts_rows(rows, fallback_items), config_name


def _postgres_fts_config_name(db: Session) -> str:
    config_name = db.scalar(
        text(
            "select case when exists ("
            "select 1 from pg_ts_config where cfgname = 'jiebacfg'"
            ") then 'jiebacfg' else 'simple' end"
        )
    )
    return str(config_name or "simple")


def _keyword_matches_from_fts_rows(rows, fallback_items: list[object]) -> list[KeywordMatch]:
    by_id = _item_lookup(fallback_items)
    matches: list[KeywordMatch] = []
    for row in rows:
        item = by_id.get(str(row["item_id"]))
        if not item:
            continue
        breakdown = {
            "title": float(row["title_rank"] or 0.0) * FTS_FIELD_WEIGHTS["title"],
            "tags": float(row["tags_rank"] or 0.0) * FTS_FIELD_WEIGHTS["tags"],
            "body": float(row["body_rank"] or 0.0) * FTS_FIELD_WEIGHTS["body"],
            "source": float(row["source_rank"] or 0.0) * FTS_FIELD_WEIGHTS["source"],
            "collection": float(row["collection_rank"] or 0.0) * FTS_FIELD_WEIGHTS["collection"],
        }
        score = sum(breakdown.values())
        if score > 0:
            matches.append(KeywordMatch(score=score, item=item, breakdown=breakdown))
    return sorted(matches, key=lambda value: value.score, reverse=True)


def _item_lookup(items: list[object]) -> dict[str, object]:
    lookup = {}
    for item in items:
        key = _id_key(item)
        lookup[key] = item
        lookup[_uuid_text_key(key)] = item
    return lookup


def _id_key(item: object) -> str:
    return str(getattr(item, "id"))


def _uuid_text_key(value: str) -> str:
    return value.replace("-", "")


def _merge_keyword_matches(primary: list[KeywordMatch], fallback: list[KeywordMatch]) -> list[KeywordMatch]:
    merged: dict[str, KeywordMatch] = {_id_key(match.item): match for match in primary}
    for match in fallback:
        key = _id_key(match.item)
        if key not in merged:
            merged[key] = match
    return sorted(merged.values(), key=lambda value: value.score, reverse=True)


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


def _merge_scores_rrf(primary, secondary):
    keyword_ranks = _score_rank_lookup(primary)
    vector_ranks = _score_rank_lookup(secondary)
    items: dict[str, object] = {}
    for _, item in primary:
        items[str(item.id)] = item
    for _, item in secondary:
        items[str(item.id)] = item
    merged = [
        (_rrf_score(keyword_ranks.get(item_id), vector_ranks.get(item_id)), item)
        for item_id, item in items.items()
    ]
    return sorted(merged, key=lambda value: value[0], reverse=True)


def _score_rank_lookup(scored) -> dict[str, int]:
    ordered = sorted(scored, key=lambda value: value[0], reverse=True)
    return {str(item.id): rank for rank, (_, item) in enumerate(ordered, start=1)}


def _rrf_score(keyword_rank: int | None, vector_rank: int | None) -> float:
    score = 0.0
    if keyword_rank is not None:
        score += RRF_KEYWORD_WEIGHT / (RRF_K + keyword_rank)
    if vector_rank is not None:
        score += RRF_VECTOR_WEIGHT / (RRF_K + vector_rank)
    return score


def _debug_question_matches(
    items: list[QuestionBankItem],
    keyword_scores: dict[str, float],
    vector_scores: dict[str, float],
    keyword_breakdowns: dict[str, dict[str, float]],
    keyword_ranks: dict[str, int],
    vector_ranks: dict[str, int],
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
            total_score=_rrf_score(keyword_ranks.get(str(item.id)), vector_ranks.get(str(item.id))),
            tags=item.tags_json or [],
            keyword_score_breakdown=keyword_breakdowns.get(str(item.id), _empty_keyword_breakdown()),
            keyword_rank=keyword_ranks.get(str(item.id)),
            vector_rank=vector_ranks.get(str(item.id)),
        )
        for item in items
        if keyword_scores.get(str(item.id), 0.0) or vector_scores.get(str(item.id), 0.0)
    ]
    return sorted(matches, key=lambda value: value.total_score, reverse=True)[:limit]


def _debug_chunk_matches(
    items: list[KnowledgeChunk],
    keyword_scores: dict[str, float],
    vector_scores: dict[str, float],
    keyword_breakdowns: dict[str, dict[str, float]],
    keyword_ranks: dict[str, int],
    vector_ranks: dict[str, int],
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
            total_score=_rrf_score(keyword_ranks.get(str(chunk.id)), vector_ranks.get(str(chunk.id))),
            tags=chunk.tags_json or [],
            source_ref=chunk.source_ref,
            keyword_score_breakdown=keyword_breakdowns.get(str(chunk.id), _empty_keyword_breakdown()),
            keyword_rank=keyword_ranks.get(str(chunk.id)),
            vector_rank=vector_ranks.get(str(chunk.id)),
        )
        for chunk in items
        if keyword_scores.get(str(chunk.id), 0.0) or vector_scores.get(str(chunk.id), 0.0)
    ]
    return sorted(matches, key=lambda value: value.total_score, reverse=True)[:limit]


def _score_question_item(item: QuestionBankItem, terms: list[str], query: str) -> dict[str, float]:
    return {
        "title": _score_field(
            " ".join([item.stem, item.knowledge_point]),
            terms,
            query,
            PYTHON_FIELD_WEIGHTS["title"],
        ),
        "tags": _score_field(
            " ".join(item.tags_json or []),
            terms,
            query,
            PYTHON_FIELD_WEIGHTS["tags"],
        ),
        "body": _score_field(
            " ".join(
                [
                    item.explanation,
                    item.difficulty,
                    " ".join(item.options_json),
                ]
            ),
            terms,
            query,
            PYTHON_FIELD_WEIGHTS["body"],
        ),
        "source": 0.0,
        "collection": _score_collection(getattr(item, "collection", None), terms, query),
    }


def _score_chunk(chunk: KnowledgeChunk, terms: list[str], query: str) -> dict[str, float]:
    return {
        "title": _score_field(chunk.title, terms, query, PYTHON_FIELD_WEIGHTS["title"]),
        "tags": _score_field(
            " ".join(chunk.tags_json or []),
            terms,
            query,
            PYTHON_FIELD_WEIGHTS["tags"],
        ),
        "body": _score_field(chunk.content, terms, query, PYTHON_FIELD_WEIGHTS["body"]),
        "source": _score_field(chunk.source_ref, terms, query, PYTHON_FIELD_WEIGHTS["source"]),
        "collection": _score_collection(getattr(chunk, "collection", None), terms, query),
    }


def _score_collection(collection: object | None, terms: list[str], query: str) -> float:
    if not collection:
        return 0.0
    return _score_field(
        " ".join(
            [
                getattr(collection, "title", ""),
                getattr(collection, "description", ""),
                " ".join(getattr(collection, "tags_json", []) or []),
            ]
        ),
        terms,
        query,
        PYTHON_FIELD_WEIGHTS["collection"],
    )


def _score_field(text: str, terms: list[str], query: str, weight: float) -> float:
    target = text.lower()
    score = 0.0
    normalized_query = query.strip().lower()
    if normalized_query and normalized_query in target:
        score += weight
    for term in terms:
        if term in target:
            score += _score_term(target, term, weight)
    return score


def _score_term(target: str, term: str, weight: float) -> float:
    if not term:
        return 0.0
    occurrence_count = min(target.count(term), 3)
    if occurrence_count <= 0:
        return 0.0
    exact_multiplier = 0.8 if re.search(rf"(?<![a-zA-Z0-9_]){re.escape(term)}(?![a-zA-Z0-9_])", target) else 0.45
    short_term_boost = 1.2 if re.fullmatch(r"[a-zA-Z0-9_]{2,8}", term) else 1.0
    return weight * exact_multiplier * short_term_boost * (1 + (occurrence_count - 1) * 0.25)


def _empty_keyword_breakdown() -> dict[str, float]:
    return {key: 0.0 for key in KEYWORD_DEBUG_KEYS}
