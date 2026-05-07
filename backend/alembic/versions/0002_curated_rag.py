from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_curated_rag"
down_revision = "0001_current_schema"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _column_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    if "retrieval_version" not in _column_names("learning_records"):
        op.add_column(
            "learning_records",
            sa.Column("retrieval_version", sa.String(length=40), nullable=True),
        )

    if not _table_exists("knowledge_collections"):
        op.create_table(
            "knowledge_collections",
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("description", sa.String(length=600), nullable=False),
            sa.Column("source_type", sa.String(length=40), nullable=False),
            sa.Column("tags_json", sa.JSON(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        "ix_knowledge_collections_source_active",
        "knowledge_collections",
        ["source_type", "is_active"],
    )

    if not _table_exists("knowledge_chunks"):
        op.create_table(
            "knowledge_chunks",
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("collection_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("title", sa.String(length=160), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("source_ref", sa.String(length=200), nullable=False),
            sa.Column("tags_json", sa.JSON(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["collection_id"], ["knowledge_collections.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        "ix_knowledge_chunks_collection_active",
        "knowledge_chunks",
        ["collection_id", "is_active"],
    )

    if not _table_exists("question_bank_items"):
        op.create_table(
            "question_bank_items",
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("collection_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("stem", sa.String(length=300), nullable=False),
            sa.Column("options_json", sa.JSON(), nullable=False),
            sa.Column("answer_index", sa.Integer(), nullable=False),
            sa.Column("explanation", sa.String(length=600), nullable=False),
            sa.Column("knowledge_point", sa.String(length=80), nullable=False),
            sa.Column("difficulty", sa.String(length=24), nullable=False),
            sa.Column("tags_json", sa.JSON(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["collection_id"], ["knowledge_collections.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        "ix_question_bank_items_collection_active",
        "question_bank_items",
        ["collection_id", "is_active"],
    )


def downgrade() -> None:
    if _table_exists("question_bank_items"):
        op.drop_index("ix_question_bank_items_collection_active", table_name="question_bank_items")
        op.drop_table("question_bank_items")
    if _table_exists("knowledge_chunks"):
        op.drop_index("ix_knowledge_chunks_collection_active", table_name="knowledge_chunks")
        op.drop_table("knowledge_chunks")
    if _table_exists("knowledge_collections"):
        op.drop_index("ix_knowledge_collections_source_active", table_name="knowledge_collections")
        op.drop_table("knowledge_collections")
    if "retrieval_version" in _column_names("learning_records"):
        op.drop_column("learning_records", "retrieval_version")
