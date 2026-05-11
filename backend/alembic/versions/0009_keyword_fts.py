from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_keyword_fts"
down_revision = "0008_knowledge_documents"
branch_labels = None
depends_on = None


QUESTION_INDEX = "ix_question_bank_items_keyword_fts"
CHUNK_INDEX = "ix_knowledge_chunks_keyword_fts"


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _index_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _fts_config_name() -> str:
    bind = op.get_bind()
    is_available = bind.scalar(
        sa.text("select exists (select 1 from pg_available_extensions where name = 'pg_jieba')")
    )
    if is_available:
        try:
            with op.get_context().autocommit_block():
                op.execute("create extension if not exists pg_jieba")
        except Exception:
            pass
    value = bind.scalar(
        sa.text(
            "select case when exists ("
            "select 1 from pg_ts_config where cfgname = 'jiebacfg'"
            ") then 'jiebacfg' else 'simple' end"
        )
    )
    return str(value or "simple")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    config_name = _fts_config_name()

    if _table_exists("question_bank_items") and QUESTION_INDEX not in _index_names("question_bank_items"):
        op.execute(
            f"""
            create index {QUESTION_INDEX}
            on question_bank_items using gin (
              (
                setweight(to_tsvector('{config_name}', coalesce(stem, '') || ' ' || coalesce(knowledge_point, '')), 'A') ||
                setweight(to_tsvector('{config_name}', coalesce(tags_json::text, '')), 'A') ||
                setweight(to_tsvector('{config_name}', coalesce(options_json::text, '') || ' ' || coalesce(explanation, '') || ' ' || coalesce(difficulty, '')), 'B')
              )
            )
            """
        )

    if _table_exists("knowledge_chunks") and CHUNK_INDEX not in _index_names("knowledge_chunks"):
        op.execute(
            f"""
            create index {CHUNK_INDEX}
            on knowledge_chunks using gin (
              (
                setweight(to_tsvector('{config_name}', coalesce(title, '')), 'A') ||
                setweight(to_tsvector('{config_name}', coalesce(tags_json::text, '')), 'A') ||
                setweight(to_tsvector('{config_name}', coalesce(content, '')), 'B') ||
                setweight(to_tsvector('{config_name}', coalesce(source_ref, '')), 'D')
              )
            )
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    if _table_exists("knowledge_chunks") and CHUNK_INDEX in _index_names("knowledge_chunks"):
        op.drop_index(CHUNK_INDEX, table_name="knowledge_chunks")
    if _table_exists("question_bank_items") and QUESTION_INDEX in _index_names("question_bank_items"):
        op.drop_index(QUESTION_INDEX, table_name="question_bank_items")
