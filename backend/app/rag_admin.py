from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .curated_import import normalize_tags
from .embeddings import EmbeddingClient, chunk_embedding_text, content_hash, question_embedding_text
from .errors import ApiHttpError
from .models import KnowledgeChunk, KnowledgeCollection, KnowledgeDocument, QuestionBankItem, now_utc
from .schemas import (
    RagAdminChunkItem,
    RagAdminChunkListResponse,
    RagAdminChunkUpdateRequest,
    RagAdminCollectionItem,
    RagAdminCollectionListResponse,
    RagAdminCollectionUpdateRequest,
    RagAdminDocumentItem,
    RagAdminDocumentListResponse,
    RagAdminDocumentUpdateRequest,
    RagAdminQuestionItem,
    RagAdminQuestionListResponse,
    RagAdminQuestionUpdateRequest,
    RagAdminReembedResponse,
)


def list_admin_collections(db: Session) -> RagAdminCollectionListResponse:
    collections = db.scalars(
        select(KnowledgeCollection).order_by(KnowledgeCollection.updated_at.desc())
    ).all()
    return RagAdminCollectionListResponse(
        items=[_collection_item(db, collection) for collection in collections]
    )


def update_admin_collection(
    db: Session,
    collection_id: str,
    payload: RagAdminCollectionUpdateRequest,
) -> RagAdminCollectionItem:
    collection = _get_collection(db, collection_id)
    fields = payload.model_fields_set
    if "description" in fields and payload.description is not None:
        collection.description = payload.description.strip()
    if "tags" in fields and payload.tags is not None:
        collection.tags_json = normalize_tags(payload.tags)
    if "isActive" in fields and payload.isActive is not None:
        collection.is_active = payload.isActive
    collection.updated_at = now_utc()
    db.commit()
    db.refresh(collection)
    return _collection_item(db, collection)


def list_admin_documents(
    db: Session,
    *,
    collection_id: str | None,
    q: str | None,
    status: str | None,
    is_active: bool | None,
    limit: int,
    offset: int,
) -> RagAdminDocumentListResponse:
    stmt = select(KnowledgeDocument).join(KnowledgeDocument.collection)
    if collection_id:
        stmt = stmt.where(KnowledgeDocument.collection_id == collection_id)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                KnowledgeDocument.title.ilike(pattern),
                KnowledgeDocument.source_uri.ilike(pattern),
            )
        )
    if status:
        stmt = stmt.where(KnowledgeDocument.status == status.strip())
    if is_active is not None:
        stmt = stmt.where(KnowledgeDocument.is_active.is_(is_active))

    total = _total(db, stmt)
    documents = db.scalars(
        stmt.order_by(KnowledgeDocument.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return RagAdminDocumentListResponse(
        items=[_document_item(db, document) for document in documents],
        total=total,
        limit=limit,
        offset=offset,
    )


def update_admin_document(
    db: Session,
    document_id: str,
    payload: RagAdminDocumentUpdateRequest,
) -> RagAdminDocumentItem:
    document = _get_document(db, document_id)
    fields = payload.model_fields_set
    if "title" in fields and payload.title is not None:
        document.title = payload.title.strip()
    if "sourceUri" in fields and payload.sourceUri is not None:
        document.source_uri = payload.sourceUri.strip()
    if "metadata" in fields and payload.metadata is not None:
        document.metadata_json = payload.metadata
    if "status" in fields and payload.status is not None:
        document.status = payload.status.strip()
    if "isActive" in fields and payload.isActive is not None:
        document.is_active = payload.isActive
    document.updated_at = now_utc()
    db.commit()
    db.refresh(document)
    return _document_item(db, document)


def list_admin_chunks(
    db: Session,
    *,
    collection_id: str | None,
    document_id: str | None,
    q: str | None,
    is_active: bool | None,
    limit: int,
    offset: int,
) -> RagAdminChunkListResponse:
    stmt = select(KnowledgeChunk).join(KnowledgeChunk.collection).outerjoin(KnowledgeChunk.document)
    if collection_id:
        stmt = stmt.where(KnowledgeChunk.collection_id == collection_id)
    if document_id:
        stmt = stmt.where(KnowledgeChunk.document_id == document_id)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                KnowledgeChunk.title.ilike(pattern),
                KnowledgeChunk.content.ilike(pattern),
                KnowledgeChunk.source_ref.ilike(pattern),
            )
        )
    if is_active is not None:
        stmt = stmt.where(KnowledgeChunk.is_active.is_(is_active))

    total = _total(db, stmt)
    chunks = db.scalars(stmt.order_by(KnowledgeChunk.created_at.desc()).limit(limit).offset(offset)).all()
    return RagAdminChunkListResponse(
        items=[_chunk_item(chunk) for chunk in chunks],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_admin_chunk(db: Session, chunk_id: str) -> RagAdminChunkItem:
    return _chunk_item(_get_chunk(db, chunk_id))


def update_admin_chunk(
    db: Session,
    chunk_id: str,
    payload: RagAdminChunkUpdateRequest,
) -> RagAdminChunkItem:
    chunk = _get_chunk(db, chunk_id)
    fields = payload.model_fields_set
    clears_embedding = False
    if "title" in fields and payload.title is not None:
        chunk.title = payload.title.strip()
        clears_embedding = True
    if "content" in fields and payload.content is not None:
        chunk.content = payload.content.strip()
        clears_embedding = True
    if "sourceRef" in fields and payload.sourceRef is not None:
        chunk.source_ref = payload.sourceRef.strip()
        clears_embedding = True
    if "tags" in fields and payload.tags is not None:
        chunk.tags_json = normalize_tags(payload.tags)
        clears_embedding = True
    if "isActive" in fields and payload.isActive is not None:
        chunk.is_active = payload.isActive
    if clears_embedding:
        _clear_embedding(chunk)
    db.commit()
    db.refresh(chunk)
    return _chunk_item(chunk)


def reembed_admin_chunk(
    db: Session,
    chunk_id: str,
    embedding_client: EmbeddingClient,
) -> RagAdminReembedResponse:
    if not embedding_client.is_enabled:
        raise ApiHttpError(400, "embedding_disabled", "Embedding 服务未配置")
    chunk = _get_chunk(db, chunk_id)
    text = chunk_embedding_text(chunk)
    digest = content_hash(text)
    embedding = embedding_client.embed_query(text)
    chunk.embedding = embedding
    chunk.embedding_model = embedding_client.model_name
    chunk.embedding_version = embedding_client.version
    chunk.content_hash = digest
    chunk.embedded_at = now_utc()
    db.commit()
    db.refresh(chunk)
    return _reembed_response(chunk)


def list_admin_questions(
    db: Session,
    *,
    collection_id: str | None,
    q: str | None,
    is_active: bool | None,
    limit: int,
    offset: int,
) -> RagAdminQuestionListResponse:
    stmt = select(QuestionBankItem).join(QuestionBankItem.collection)
    if collection_id:
        stmt = stmt.where(QuestionBankItem.collection_id == collection_id)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                QuestionBankItem.stem.ilike(pattern),
                QuestionBankItem.explanation.ilike(pattern),
                QuestionBankItem.knowledge_point.ilike(pattern),
            )
        )
    if is_active is not None:
        stmt = stmt.where(QuestionBankItem.is_active.is_(is_active))

    total = _total(db, stmt)
    questions = db.scalars(
        stmt.order_by(QuestionBankItem.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return RagAdminQuestionListResponse(
        items=[_question_item(question) for question in questions],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_admin_question(db: Session, question_id: str) -> RagAdminQuestionItem:
    return _question_item(_get_question(db, question_id))


def update_admin_question(
    db: Session,
    question_id: str,
    payload: RagAdminQuestionUpdateRequest,
) -> RagAdminQuestionItem:
    question = _get_question(db, question_id)
    fields = payload.model_fields_set
    clears_embedding = False
    if "difficulty" in fields and payload.difficulty is not None:
        question.difficulty = payload.difficulty.strip()
        clears_embedding = True
    if "tags" in fields and payload.tags is not None:
        question.tags_json = normalize_tags(payload.tags)
        clears_embedding = True
    if "isActive" in fields and payload.isActive is not None:
        question.is_active = payload.isActive
    if clears_embedding:
        _clear_embedding(question)
    question.updated_at = now_utc()
    db.commit()
    db.refresh(question)
    return _question_item(question)


def reembed_admin_question(
    db: Session,
    question_id: str,
    embedding_client: EmbeddingClient,
) -> RagAdminReembedResponse:
    if not embedding_client.is_enabled:
        raise ApiHttpError(400, "embedding_disabled", "Embedding 服务未配置")
    question = _get_question(db, question_id)
    text = question_embedding_text(question)
    digest = content_hash(text)
    embedding = embedding_client.embed_query(text)
    question.embedding = embedding
    question.embedding_model = embedding_client.model_name
    question.embedding_version = embedding_client.version
    question.content_hash = digest
    question.embedded_at = now_utc()
    db.commit()
    db.refresh(question)
    return _reembed_response(question)


def _total(db: Session, stmt) -> int:
    return int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)


def _collection_item(db: Session, collection: KnowledgeCollection) -> RagAdminCollectionItem:
    return RagAdminCollectionItem(
        id=str(collection.id),
        title=collection.title,
        description=collection.description,
        sourceType=collection.source_type,
        tags=collection.tags_json or [],
        isActive=collection.is_active,
        documentCount=_count(db, KnowledgeDocument, KnowledgeDocument.collection_id == collection.id),
        chunkCount=_count(db, KnowledgeChunk, KnowledgeChunk.collection_id == collection.id),
        questionCount=_count(db, QuestionBankItem, QuestionBankItem.collection_id == collection.id),
        createdAt=collection.created_at,
        updatedAt=collection.updated_at,
    )


def _document_item(db: Session, document: KnowledgeDocument) -> RagAdminDocumentItem:
    return RagAdminDocumentItem(
        id=str(document.id),
        collectionId=str(document.collection_id),
        collectionTitle=getattr(document.collection, "title", ""),
        title=document.title,
        sourceType=document.source_type,
        sourceUri=document.source_uri,
        contentHash=document.content_hash,
        metadata=document.metadata_json or {},
        status=document.status,
        isActive=document.is_active,
        chunkCount=_count(db, KnowledgeChunk, KnowledgeChunk.document_id == document.id),
        createdAt=document.created_at,
        updatedAt=document.updated_at,
    )


def _chunk_item(chunk: KnowledgeChunk) -> RagAdminChunkItem:
    return RagAdminChunkItem(
        id=str(chunk.id),
        collectionId=str(chunk.collection_id),
        collectionTitle=getattr(chunk.collection, "title", ""),
        documentId=str(chunk.document_id) if chunk.document_id else None,
        documentTitle=getattr(chunk.document, "title", None),
        title=chunk.title,
        content=chunk.content,
        sourceRef=chunk.source_ref,
        tags=chunk.tags_json or [],
        isActive=chunk.is_active,
        embeddingModel=chunk.embedding_model,
        embeddingVersion=chunk.embedding_version,
        contentHash=chunk.content_hash,
        embeddedAt=chunk.embedded_at,
        createdAt=chunk.created_at,
    )


def _question_item(question: QuestionBankItem) -> RagAdminQuestionItem:
    return RagAdminQuestionItem(
        id=str(question.id),
        collectionId=str(question.collection_id),
        collectionTitle=getattr(question.collection, "title", ""),
        stem=question.stem,
        options=question.options_json,
        answerIndex=question.answer_index,
        answerIndexes=question.answer_indexes_json,
        questionType=question.question_type,
        explanation=question.explanation,
        knowledgePoint=question.knowledge_point,
        difficulty=question.difficulty,
        tags=question.tags_json or [],
        isActive=question.is_active,
        embeddingModel=question.embedding_model,
        embeddingVersion=question.embedding_version,
        contentHash=question.content_hash,
        embeddedAt=question.embedded_at,
        createdAt=question.created_at,
        updatedAt=question.updated_at,
    )


def _count(db: Session, model: type, condition: Any) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(condition)) or 0)


def _get_collection(db: Session, collection_id: str) -> KnowledgeCollection:
    collection = db.get(KnowledgeCollection, collection_id)
    if not collection:
        raise ApiHttpError(404, "rag_admin_not_found", "知识库不存在")
    return collection


def _get_document(db: Session, document_id: str) -> KnowledgeDocument:
    document = db.get(KnowledgeDocument, document_id)
    if not document:
        raise ApiHttpError(404, "rag_admin_not_found", "资料来源不存在")
    return document


def _get_chunk(db: Session, chunk_id: str) -> KnowledgeChunk:
    chunk = db.get(KnowledgeChunk, chunk_id)
    if not chunk:
        raise ApiHttpError(404, "rag_admin_not_found", "知识片段不存在")
    return chunk


def _get_question(db: Session, question_id: str) -> QuestionBankItem:
    question = db.get(QuestionBankItem, question_id)
    if not question:
        raise ApiHttpError(404, "rag_admin_not_found", "题库题目不存在")
    return question


def _clear_embedding(item: KnowledgeChunk | QuestionBankItem) -> None:
    item.embedding = None
    item.embedding_model = None
    item.embedding_version = None
    item.content_hash = None
    item.embedded_at = None


def _reembed_response(item: KnowledgeChunk | QuestionBankItem) -> RagAdminReembedResponse:
    return RagAdminReembedResponse(
        id=str(item.id),
        embeddingModel=item.embedding_model or "",
        embeddingVersion=item.embedding_version or "",
        contentHash=item.content_hash or "",
        embeddedAt=item.embedded_at or now_utc(),
    )
