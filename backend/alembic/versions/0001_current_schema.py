from __future__ import annotations

from collections.abc import Iterable

from alembic import op
import sqlalchemy as sa


revision = "0001_current_schema"
down_revision = None
branch_labels = None
depends_on = None
QUIZ_PROMPT_VERSION = "quiz-v1"
REPORT_PROMPT_VERSION = "report-v1"


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


def _unique_constraint_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints(table_name)
        if constraint["name"]
    }


def _add_columns_if_missing(table_name: str, columns: Iterable[sa.Column]) -> None:
    existing_columns = _column_names(table_name)
    for column in columns:
        if column.name not in existing_columns:
            op.add_column(table_name, column)


def _create_index_if_missing(
    index_name: str,
    table_name: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    if index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def _create_unique_constraint_if_missing(
    constraint_name: str,
    table_name: str,
    columns: list[str],
) -> None:
    if constraint_name not in _unique_constraint_names(table_name):
        op.create_unique_constraint(constraint_name, table_name, columns)


def upgrade() -> None:
    if not _table_exists("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("openid", sa.String(length=128), nullable=False),
            sa.Column("unionid", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_users_openid", "users", ["openid"], unique=True)

    if not _table_exists("learning_records"):
        op.create_table(
            "learning_records",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("user_id", sa.String(length=32), nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("topic", sa.String(length=120), nullable=False),
            sa.Column("questions_json", sa.JSON(), nullable=False),
            sa.Column("answers_json", sa.JSON(), nullable=False),
            sa.Column("report_json", sa.JSON(), nullable=False),
            sa.Column("score", sa.Integer(), nullable=False),
            sa.Column("total", sa.Integer(), nullable=False),
            sa.Column("accuracy_percent", sa.Integer(), nullable=False),
            sa.Column(
                "quiz_prompt_version",
                sa.String(length=40),
                nullable=False,
                server_default=QUIZ_PROMPT_VERSION,
            ),
            sa.Column(
                "quiz_model_name",
                sa.String(length=120),
                nullable=False,
                server_default="",
            ),
            sa.Column(
                "report_prompt_version",
                sa.String(length=40),
                nullable=False,
                server_default=REPORT_PROMPT_VERSION,
            ),
            sa.Column(
                "report_model_name",
                sa.String(length=120),
                nullable=False,
                server_default="",
            ),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "session_id",
                name="uq_learning_records_user_session",
            ),
        )
    else:
        _add_columns_if_missing(
            "learning_records",
            [
                sa.Column(
                    "quiz_prompt_version",
                    sa.String(length=40),
                    nullable=False,
                    server_default=QUIZ_PROMPT_VERSION,
                ),
                sa.Column(
                    "quiz_model_name",
                    sa.String(length=120),
                    nullable=False,
                    server_default="",
                ),
                sa.Column(
                    "report_prompt_version",
                    sa.String(length=40),
                    nullable=False,
                    server_default=REPORT_PROMPT_VERSION,
                ),
                sa.Column(
                    "report_model_name",
                    sa.String(length=120),
                    nullable=False,
                    server_default="",
                ),
            ],
        )
        _create_unique_constraint_if_missing(
            "uq_learning_records_user_session",
            "learning_records",
            ["user_id", "session_id"],
        )
    _create_index_if_missing(
        "ix_learning_records_user_completed",
        "learning_records",
        ["user_id", "completed_at"],
    )

    if not _table_exists("question_feedback"):
        op.create_table(
            "question_feedback",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("user_id", sa.String(length=32), nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("topic", sa.String(length=120), nullable=False),
            sa.Column("question_id", sa.String(length=128), nullable=False),
            sa.Column("reason", sa.String(length=40), nullable=False),
            sa.Column("question_json", sa.JSON(), nullable=False),
            sa.Column("selected_index", sa.Integer(), nullable=True),
            sa.Column("source_page", sa.String(length=24), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "session_id",
                "question_id",
                "reason",
                name="uq_question_feedback_user_session_question_reason",
            ),
        )
    else:
        _create_unique_constraint_if_missing(
            "uq_question_feedback_user_session_question_reason",
            "question_feedback",
            ["user_id", "session_id", "question_id", "reason"],
        )
    _create_index_if_missing(
        "ix_question_feedback_user_created",
        "question_feedback",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    if _table_exists("question_feedback"):
        op.drop_index("ix_question_feedback_user_created", table_name="question_feedback")
        op.drop_table("question_feedback")

    if _table_exists("learning_records"):
        op.drop_index("ix_learning_records_user_completed", table_name="learning_records")
        op.drop_table("learning_records")

    if _table_exists("users"):
        op.drop_index("ix_users_openid", table_name="users")
        op.drop_table("users")
