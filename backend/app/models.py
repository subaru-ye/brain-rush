from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .prompts import QUIZ_PROMPT_VERSION, REPORT_PROMPT_VERSION


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
    question_items: Mapped[list["QuestionBankItem"]] = relationship(back_populates="collection")


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
    tags_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    collection: Mapped[KnowledgeCollection] = relationship(back_populates="chunks")


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
