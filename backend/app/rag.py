from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import KnowledgeChunk, QuestionBankItem
from .quiz_answers import format_option_indexes
from .schemas import QuizQuestion


RETRIEVAL_VERSION = "curated-rag-v1"


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


def retrieve_curated_context(db: Session, query: str) -> RetrievedContext:
    terms = _search_terms(query)
    if not terms:
        return RetrievedContext()

    question_items = db.scalars(
        select(QuestionBankItem).where(QuestionBankItem.is_active.is_(True)).limit(300)
    ).all()
    chunks = db.scalars(
        select(KnowledgeChunk).where(KnowledgeChunk.is_active.is_(True)).limit(300)
    ).all()

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
    return RetrievedContext(
        question_items=[item for _, item in scored_questions[:5]],
        chunks=[chunk for _, chunk in scored_chunks[:5]],
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
