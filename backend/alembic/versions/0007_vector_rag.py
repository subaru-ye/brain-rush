from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "0007_vector_rag"
down_revision = "0006_remaining_uuid_ids"
branch_labels = None
depends_on = None


EMBEDDING_DIMENSIONS = 1536
VECTOR_TABLES = ("knowledge_chunks", "question_bank_items")


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _column_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_vector_columns(table_name: str) -> None:
    columns = _column_names(table_name)
    if "embedding" not in columns:
        op.add_column(table_name, sa.Column("embedding", Vector(EMBEDDING_DIMENSIONS), nullable=True))
    if "embedding_model" not in columns:
        op.add_column(table_name, sa.Column("embedding_model", sa.String(length=120), nullable=True))
    if "embedding_version" not in columns:
        op.add_column(table_name, sa.Column("embedding_version", sa.String(length=40), nullable=True))
    if "content_hash" not in columns:
        op.add_column(table_name, sa.Column("content_hash", sa.String(length=64), nullable=True))
    if "embedded_at" not in columns:
        op.add_column(table_name, sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True))


def _drop_vector_columns(table_name: str) -> None:
    columns = _column_names(table_name)
    for column_name in (
        "embedded_at",
        "content_hash",
        "embedding_version",
        "embedding_model",
        "embedding",
    ):
        if column_name in columns:
            op.drop_column(table_name, column_name)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("create extension if not exists vector")
    for table_name in VECTOR_TABLES:
        if _table_exists(table_name):
            _add_vector_columns(table_name)

    op.execute(
        "create index if not exists ix_knowledge_chunks_embedding_cosine "
        "on knowledge_chunks using ivfflat (embedding vector_cosine_ops) "
        "with (lists = 100) where embedding is not null"
    )
    op.execute(
        "create index if not exists ix_question_bank_items_embedding_cosine "
        "on question_bank_items using ivfflat (embedding vector_cosine_ops) "
        "with (lists = 100) where embedding is not null"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("drop index if exists ix_question_bank_items_embedding_cosine")
    op.execute("drop index if exists ix_knowledge_chunks_embedding_cosine")
    for table_name in VECTOR_TABLES:
        if _table_exists(table_name):
            _drop_vector_columns(table_name)
