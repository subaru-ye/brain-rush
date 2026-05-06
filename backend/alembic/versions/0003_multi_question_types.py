from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_multi_question_types"
down_revision = "0002_curated_rag"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _column_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    if _table_exists("question_bank_items"):
        columns = _column_names("question_bank_items")
        if "question_type" not in columns:
            op.add_column(
                "question_bank_items",
                sa.Column(
                    "question_type",
                    sa.String(length=32),
                    nullable=False,
                    server_default="single_choice",
                ),
            )
        if "answer_indexes_json" not in columns:
            op.add_column(
                "question_bank_items",
                sa.Column("answer_indexes_json", sa.JSON(), nullable=True),
            )
            bind = op.get_bind()
            if bind.dialect.name == "postgresql":
                bind.execute(
                    sa.text(
                        "update question_bank_items "
                        "set answer_indexes_json = json_build_array(answer_index)"
                    )
                )
            else:
                bind.execute(
                    sa.text(
                        "update question_bank_items "
                        "set answer_indexes_json = json_array(answer_index)"
                    )
                )
            op.alter_column("question_bank_items", "answer_indexes_json", nullable=False)

    if _table_exists("question_feedback"):
        columns = _column_names("question_feedback")
        if "selected_indexes_json" not in columns:
            op.add_column(
                "question_feedback",
                sa.Column("selected_indexes_json", sa.JSON(), nullable=True),
            )
            bind = op.get_bind()
            if bind.dialect.name == "postgresql":
                bind.execute(
                    sa.text(
                        "update question_feedback "
                        "set selected_indexes_json = "
                        "case when selected_index is null then '[]'::json "
                        "else json_build_array(selected_index) end"
                    )
                )
            else:
                bind.execute(
                    sa.text(
                        "update question_feedback "
                        "set selected_indexes_json = "
                        "case when selected_index is null then json_array() "
                        "else json_array(selected_index) end"
                    )
                )
            op.alter_column("question_feedback", "selected_indexes_json", nullable=False)


def downgrade() -> None:
    if _table_exists("question_feedback") and "selected_indexes_json" in _column_names(
        "question_feedback"
    ):
        op.drop_column("question_feedback", "selected_indexes_json")
    if _table_exists("question_bank_items"):
        columns = _column_names("question_bank_items")
        if "answer_indexes_json" in columns:
            op.drop_column("question_bank_items", "answer_indexes_json")
        if "question_type" in columns:
            op.drop_column("question_bank_items", "question_type")
