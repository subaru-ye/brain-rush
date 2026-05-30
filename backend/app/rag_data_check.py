from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import KnowledgeChunk, KnowledgeCollection, KnowledgeDocument, QuestionBankItem


DEFAULT_KNOWLEDGE_PATH = Path(__file__).resolve().parents[1] / "data" / "rag-knowledge.json"
KINDS = ("collections", "documents", "chunks", "questions")


@dataclass(frozen=True)
class CollectionSpec:
    title: str
    is_active: bool


@dataclass(frozen=True)
class DocumentSpec:
    collection_title: str
    title: str
    source_type: str
    source_uri: str
    is_active: bool


@dataclass(frozen=True)
class ChunkSpec:
    collection_title: str
    title: str
    document: DocumentSpec | None
    is_active: bool


@dataclass(frozen=True)
class QuestionSpec:
    collection_title: str
    stem: str
    knowledge_point: str
    is_active: bool


@dataclass(frozen=True)
class RagKnowledgeCatalog:
    collections: list[CollectionSpec]
    documents: list[DocumentSpec]
    chunks: list[ChunkSpec]
    questions: list[QuestionSpec]


def load_knowledge_catalog(path: str | Path) -> RagKnowledgeCatalog:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    collections_payload = payload.get("collections", []) if isinstance(payload, dict) else payload
    if not isinstance(collections_payload, list):
        raise ValueError("RAG knowledge file must contain a collections list")

    collections: list[CollectionSpec] = []
    documents: list[DocumentSpec] = []
    chunks: list[ChunkSpec] = []
    questions: list[QuestionSpec] = []

    for collection_payload in collections_payload:
        collection_title = _text(collection_payload.get("title"))
        if not collection_title:
            continue
        collection_is_active = _is_active(collection_payload)
        collections.append(CollectionSpec(title=collection_title, is_active=collection_is_active))

        for chunk_payload in collection_payload.get("chunks", []) or []:
            chunks.append(
                ChunkSpec(
                    collection_title=collection_title,
                    title=_text(chunk_payload.get("title")),
                    document=None,
                    is_active=collection_is_active and _is_active(chunk_payload),
                )
            )

        for document_payload in collection_payload.get("documents", []) or []:
            document = DocumentSpec(
                collection_title=collection_title,
                title=_text(document_payload.get("title")),
                source_type=_text(document_payload.get("sourceType")) or "manual",
                source_uri=_text(document_payload.get("sourceUri")),
                is_active=collection_is_active and _is_active(document_payload),
            )
            if not document.title:
                continue
            documents.append(document)
            for chunk_payload in document_payload.get("chunks", []) or []:
                chunks.append(
                    ChunkSpec(
                        collection_title=collection_title,
                        title=_text(chunk_payload.get("title")),
                        document=document,
                        is_active=document.is_active and _is_active(chunk_payload),
                    )
                )

        for question_payload in collection_payload.get("questions", []) or []:
            questions.append(
                QuestionSpec(
                    collection_title=collection_title,
                    stem=_text(question_payload.get("stem")),
                    knowledge_point=_text(question_payload.get("knowledgePoint")),
                    is_active=collection_is_active and _is_active(question_payload),
                )
            )

    return RagKnowledgeCatalog(
        collections=[item for item in collections if item.title],
        documents=documents,
        chunks=[item for item in chunks if item.title],
        questions=[item for item in questions if item.stem],
    )


def check_rag_knowledge_data(db: Session, path: str | Path = DEFAULT_KNOWLEDGE_PATH) -> dict[str, Any]:
    catalog = load_knowledge_catalog(path)
    result = _empty_result(Path(path))
    collections_by_title: dict[str, KnowledgeCollection] = {}
    documents_by_spec: dict[DocumentSpec, KnowledgeDocument | None] = {}

    for spec in catalog.collections:
        result["summary"]["expected"]["collections"] += 1
        collection = db.scalar(
            select(KnowledgeCollection).where(
                KnowledgeCollection.title == spec.title,
                KnowledgeCollection.source_type == "curated",
            )
        )
        collections_by_title[spec.title] = collection
        if not spec.is_active:
            continue
        if not collection:
            _add_issue(result, "missing", "collections", _collection_payload(spec))
        elif not collection.is_active:
            _add_issue(result, "inactive", "collections", _collection_payload(spec, collection))

    for spec in catalog.documents:
        result["summary"]["expected"]["documents"] += 1
        collection = collections_by_title.get(spec.collection_title)
        document = _find_document(db, collection, spec) if collection else None
        documents_by_spec[spec] = document
        if not spec.is_active:
            continue
        payload = _document_payload(spec, document)
        if not collection:
            payload["reason"] = "collection_missing"
            _add_issue(result, "missing", "documents", payload)
        elif not collection.is_active:
            payload["reason"] = "collection_inactive"
            _add_issue(result, "inactive", "documents", payload)
        elif not document:
            _add_issue(result, "missing", "documents", payload)
        elif not document.is_active or document.status != "active":
            _add_issue(result, "inactive", "documents", payload)
        elif document.title != spec.title:
            payload["actualTitle"] = document.title
            _add_issue(result, "titleMismatches", "documents", payload)

    for spec in catalog.chunks:
        result["summary"]["expected"]["chunks"] += 1
        if not spec.is_active:
            continue
        issue = _check_chunk(db, collections_by_title, documents_by_spec, spec)
        if issue:
            _add_issue(result, issue["group"], "chunks", issue["payload"])

    for spec in catalog.questions:
        result["summary"]["expected"]["questions"] += 1
        if not spec.is_active:
            continue
        issue = _check_question(db, collections_by_title, spec)
        if issue:
            _add_issue(result, issue["group"], "questions", issue["payload"])

    result["ok"] = not any(
        result["summary"][group][kind]
        for group in ("missing", "inactive", "titleMismatches")
        for kind in KINDS
    )
    return result


def check_rag_knowledge_file(path: str | Path = DEFAULT_KNOWLEDGE_PATH) -> dict[str, Any]:
    with SessionLocal() as db:
        return check_rag_knowledge_data(db, path)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Check imported RAG knowledge data against JSON.")
    parser.add_argument(
        "path",
        nargs="?",
        default=str(DEFAULT_KNOWLEDGE_PATH),
        help="Path to rag-knowledge.json",
    )
    args = parser.parse_args()
    print(json.dumps(check_rag_knowledge_file(args.path), ensure_ascii=False, indent=2))


def _check_chunk(
    db: Session,
    collections_by_title: dict[str, KnowledgeCollection],
    documents_by_spec: dict[DocumentSpec, KnowledgeDocument | None],
    spec: ChunkSpec,
) -> dict[str, Any] | None:
    collection = collections_by_title.get(spec.collection_title)
    document = documents_by_spec.get(spec.document) if spec.document else None
    payload = _chunk_payload(spec)
    if not collection:
        payload["reason"] = "collection_missing"
        return {"group": "missing", "payload": payload}
    if not collection.is_active:
        payload["reason"] = "collection_inactive"
        return {"group": "inactive", "payload": payload}
    if spec.document and not document:
        payload["reason"] = "document_missing"
        return {"group": "missing", "payload": payload}
    if document and (not document.is_active or document.status != "active"):
        payload["reason"] = "document_inactive"
        return {"group": "inactive", "payload": payload}

    stmt = select(KnowledgeChunk).where(
        KnowledgeChunk.collection_id == collection.id,
        KnowledgeChunk.title == spec.title,
    )
    if document:
        stmt = stmt.where(KnowledgeChunk.document_id == document.id)
    else:
        stmt = stmt.where(KnowledgeChunk.document_id.is_(None))
    chunk = db.scalar(stmt)
    if not chunk:
        return {"group": "missing", "payload": payload}
    if not chunk.is_active:
        return {"group": "inactive", "payload": payload}
    return None


def _check_question(
    db: Session,
    collections_by_title: dict[str, KnowledgeCollection],
    spec: QuestionSpec,
) -> dict[str, Any] | None:
    collection = collections_by_title.get(spec.collection_title)
    payload = _question_payload(spec)
    if not collection:
        payload["reason"] = "collection_missing"
        return {"group": "missing", "payload": payload}
    if not collection.is_active:
        payload["reason"] = "collection_inactive"
        return {"group": "inactive", "payload": payload}
    question = db.scalar(
        select(QuestionBankItem).where(
            QuestionBankItem.collection_id == collection.id,
            QuestionBankItem.stem == spec.stem,
        )
    )
    if not question:
        return {"group": "missing", "payload": payload}
    if not question.is_active:
        return {"group": "inactive", "payload": payload}
    return None


def _find_document(
    db: Session,
    collection: KnowledgeCollection | None,
    spec: DocumentSpec,
) -> KnowledgeDocument | None:
    if not collection:
        return None
    conditions = [
        KnowledgeDocument.collection_id == collection.id,
        KnowledgeDocument.source_type == spec.source_type,
    ]
    if spec.source_uri:
        conditions.append(KnowledgeDocument.source_uri == spec.source_uri)
    else:
        conditions.append(KnowledgeDocument.title == spec.title)
    return db.scalar(select(KnowledgeDocument).where(*conditions))


def _empty_result(path: Path) -> dict[str, Any]:
    return {
        "ok": False,
        "sourcePath": str(path),
        "summary": {
            "expected": {kind: 0 for kind in KINDS},
            "missing": {kind: 0 for kind in KINDS},
            "inactive": {kind: 0 for kind in KINDS},
            "titleMismatches": {kind: 0 for kind in KINDS},
        },
        "missing": {kind: [] for kind in KINDS},
        "inactive": {kind: [] for kind in KINDS},
        "titleMismatches": {kind: [] for kind in KINDS},
    }


def _add_issue(result: dict[str, Any], group: str, kind: str, payload: dict[str, Any]) -> None:
    result[group][kind].append(payload)
    result["summary"][group][kind] += 1


def _collection_payload(
    spec: CollectionSpec,
    collection: KnowledgeCollection | None = None,
) -> dict[str, Any]:
    payload = {"title": spec.title}
    if collection:
        payload["id"] = str(collection.id)
    return payload


def _document_payload(
    spec: DocumentSpec,
    document: KnowledgeDocument | None = None,
) -> dict[str, Any]:
    payload = {
        "collectionTitle": spec.collection_title,
        "title": spec.title,
        "sourceType": spec.source_type,
        "sourceUri": spec.source_uri,
    }
    if document:
        payload["id"] = str(document.id)
        payload["status"] = document.status
    return payload


def _chunk_payload(spec: ChunkSpec) -> dict[str, Any]:
    payload = {
        "collectionTitle": spec.collection_title,
        "title": spec.title,
    }
    if spec.document:
        payload["documentTitle"] = spec.document.title
        payload["documentSourceUri"] = spec.document.source_uri
    return payload


def _question_payload(spec: QuestionSpec) -> dict[str, Any]:
    return {
        "collectionTitle": spec.collection_title,
        "title": spec.stem,
        "knowledgePoint": spec.knowledge_point,
    }


def _text(value: Any) -> str:
    return str(value or "").strip()


def _is_active(payload: dict[str, Any]) -> bool:
    return bool(payload.get("isActive", True))


if __name__ == "__main__":
    main()
