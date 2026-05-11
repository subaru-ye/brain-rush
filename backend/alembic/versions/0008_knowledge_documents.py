from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_knowledge_documents"
down_revision = "0007_vector_rag"
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


def _foreign_key_names(table_name: str, constrained_column: str) -> list[str]:
    if not _table_exists(table_name):
        return []
    return [
        foreign_key["name"]
        for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys(table_name)
        if foreign_key["name"] and constrained_column in foreign_key.get("constrained_columns", [])
    ]


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    if not _table_exists("knowledge_documents"):
        op.create_table(
            "knowledge_documents",
            sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("collection_id", sa.Uuid(as_uuid=False), nullable=False),
            sa.Column("title", sa.String(length=180), nullable=False),
            sa.Column("source_type", sa.String(length=40), nullable=False),
            sa.Column("source_uri", sa.String(length=500), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["collection_id"], ["knowledge_collections.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        "ix_knowledge_documents_collection_active",
        "knowledge_documents",
        ["collection_id", "is_active"],
    )
    _create_index_if_missing(
        "ix_knowledge_documents_source_type",
        "knowledge_documents",
        ["source_type"],
    )

    if _table_exists("knowledge_chunks") and "document_id" not in _column_names("knowledge_chunks"):
        op.add_column(
            "knowledge_chunks",
            sa.Column("document_id", sa.Uuid(as_uuid=False), nullable=True),
        )
        op.create_foreign_key(
            "fk_knowledge_chunks_document_id_documents",
            "knowledge_chunks",
            "knowledge_documents",
            ["document_id"],
            ["id"],
        )


def downgrade() -> None:
    if _table_exists("knowledge_chunks") and "document_id" in _column_names("knowledge_chunks"):
        for foreign_key_name in _foreign_key_names("knowledge_chunks", "document_id"):
            op.drop_constraint(foreign_key_name, "knowledge_chunks", type_="foreignkey")
        op.drop_column("knowledge_chunks", "document_id")

    if _table_exists("knowledge_documents"):
        if "ix_knowledge_documents_source_type" in _index_names("knowledge_documents"):
            op.drop_index("ix_knowledge_documents_source_type", table_name="knowledge_documents")
        if "ix_knowledge_documents_collection_active" in _index_names("knowledge_documents"):
            op.drop_index("ix_knowledge_documents_collection_active", table_name="knowledge_documents")
        op.drop_table("knowledge_documents")
