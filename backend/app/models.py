from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from .database import Base
from .prompts import QUIZ_PROMPT_VERSION, REPORT_PROMPT_VERSION


EMBEDDING_DIMENSIONS = 1536


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid4().hex


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    openid: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    unionid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
    )

    records: Mapped[list["LearningRecord"]] = relationship(back_populates="user")
    feedback_items: Mapped[list["QuestionFeedback"]] = relationship(back_populates="user")
    product_events: Mapped[list["ProductEvent"]] = relationship(back_populates="user")


class LearningRecord(Base):
    __tablename__ = "learning_records"
    __table_args__ = (
        UniqueConstraint("user_id", "session_id", name="uq_learning_records_user_session"),
        Index("ix_learning_records_user_completed", "user_id", "completed_at"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
    questions_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    answers_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    report_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    accuracy_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    quiz_prompt_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default=QUIZ_PROMPT_VERSION,
    )
    quiz_model_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    report_prompt_version: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default=REPORT_PROMPT_VERSION,
    )
    report_model_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    retrieval_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    user: Mapped[User] = relationship(back_populates="records")


class KnowledgeCollection(Base):
    __tablename__ = "knowledge_collections"
    __table_args__ = (Index("ix_knowledge_collections_source_active", "source_type", "is_active"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(600), nullable=False, default="")
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="curated")
    tags_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
    )

    chunks: Mapped[list["KnowledgeChunk"]] = relationship(back_populates="collection")
    documents: Mapped[list["KnowledgeDocument"]] = relationship(back_populates="collection")
    question_items: Mapped[list["QuestionBankItem"]] = relationship(back_populates="collection")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        Index("ix_knowledge_documents_collection_active", "collection_id", "is_active"),
        Index("ix_knowledge_documents_source_type", "source_type"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    collection_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("knowledge_collections.id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    source_uri: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
    )

    collection: Mapped[KnowledgeCollection] = relationship(back_populates="documents")
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(back_populates="document")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (Index("ix_knowledge_chunks_collection_active", "collection_id", "is_active"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    collection_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("knowledge_collections.id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    document_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("knowledge_documents.id"),
        nullable=True,
    )
    tags_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    embedding_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    collection: Mapped[KnowledgeCollection] = relationship(back_populates="chunks")
    document: Mapped[KnowledgeDocument | None] = relationship(back_populates="chunks")


class RagImportJob(Base):
    __tablename__ = "rag_import_jobs"
    __table_args__ = (
        Index("ix_rag_import_jobs_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="upload")
    source_uri: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    file_name: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    collection_title: Mapped[str] = mapped_column(String(120), nullable=False)
    document_title: Mapped[str | None] = mapped_column(String(180), nullable=True)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1200)
    chunk_overlap: Mapped[int] = mapped_column(Integer, nullable=False, default=150)
    stats_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    queue_job_id: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QuestionBankItem(Base):
    __tablename__ = "question_bank_items"
    __table_args__ = (Index("ix_question_bank_items_collection_active", "collection_id", "is_active"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    collection_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("knowledge_collections.id"),
        nullable=False,
    )
    stem: Mapped[str] = mapped_column(String(300), nullable=False)
    options_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    answer_index: Mapped[int] = mapped_column(Integer, nullable=False)
    answer_indexes_json: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    question_type: Mapped[str] = mapped_column(String(32), nullable=False, default="single_choice")
    explanation: Mapped[str] = mapped_column(String(600), nullable=False)
    knowledge_point: Mapped[str] = mapped_column(String(80), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(24), nullable=False, default="normal")
    tags_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    embedding_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
    )

    collection: Mapped[KnowledgeCollection] = relationship(back_populates="question_items")


class QuestionFeedback(Base):
    __tablename__ = "question_feedback"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "session_id",
            "question_id",
            "reason",
            name="uq_question_feedback_user_session_question_reason",
        ),
        Index("ix_question_feedback_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
    question_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(String(40), nullable=False)
    question_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    selected_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected_indexes_json: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    source_page: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
    )

    user: Mapped[User] = relationship(back_populates="feedback_items")


class ProductEvent(Base):
    __tablename__ = "product_events"
    __table_args__ = (
        Index("ix_product_events_event_created", "event_name", "created_at"),
        Index("ix_product_events_client_created", "client_id", "created_at"),
        Index("ix_product_events_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("users.id"),
        nullable=True,
    )
    client_id: Mapped[str] = mapped_column(String(80), nullable=False)
    event_name: Mapped[str] = mapped_column(String(80), nullable=False)
    page: Mapped[str] = mapped_column(String(80), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(120), nullable=True)
    properties_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    user: Mapped[User | None] = relationship(back_populates="product_events")
