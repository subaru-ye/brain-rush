from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_user_uuid_ids"
down_revision = "0003_multi_question_types"
branch_labels = None
depends_on = None


USER_FK_TABLES = ("learning_records", "question_feedback")


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _column_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _column_type_name(table_name: str, column_name: str) -> str | None:
    if not _table_exists(table_name):
        return None
    for column in sa.inspect(op.get_bind()).get_columns(table_name):
        if column["name"] == column_name:
            return str(column["type"]).lower()
    return None


def _foreign_key_names(table_name: str, referred_table: str) -> list[str]:
    if not _table_exists(table_name):
        return []
    return [
        foreign_key["name"]
        for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys(table_name)
        if foreign_key["name"] and foreign_key.get("referred_table") == referred_table
    ]


def _drop_user_foreign_keys() -> None:
    for table_name in USER_FK_TABLES:
        for foreign_key_name in _foreign_key_names(table_name, "users"):
            op.drop_constraint(foreign_key_name, table_name, type_="foreignkey")


def _create_user_foreign_keys() -> None:
    if _table_exists("learning_records"):
        op.create_foreign_key(
            "fk_learning_records_user_id_users",
            "learning_records",
            "users",
            ["user_id"],
            ["id"],
        )
    if _table_exists("question_feedback"):
        op.create_foreign_key(
            "fk_question_feedback_user_id_users",
            "question_feedback",
            "users",
            ["user_id"],
            ["id"],
        )


def _alter_to_uuid(table_name: str, column_name: str) -> None:
    if column_name not in _column_names(table_name):
        return
    if _column_type_name(table_name, column_name) == "uuid":
        return
    op.alter_column(
        table_name,
        column_name,
        existing_type=sa.String(length=32),
        type_=sa.Uuid(as_uuid=False),
        postgresql_using=f"{column_name}::uuid",
    )


def _alter_to_string(table_name: str, column_name: str) -> None:
    if column_name not in _column_names(table_name):
        return
    if _column_type_name(table_name, column_name) != "uuid":
        return
    op.alter_column(
        table_name,
        column_name,
        existing_type=sa.Uuid(as_uuid=False),
        type_=sa.String(length=32),
        postgresql_using=f"replace({column_name}::text, '-', '')",
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql" or not _table_exists("users"):
        return

    _drop_user_foreign_keys()

    _alter_to_uuid("learning_records", "user_id")
    _alter_to_uuid("question_feedback", "user_id")
    _alter_to_uuid("users", "id")

    _create_user_foreign_keys()


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql" or not _table_exists("users"):
        return

    _drop_user_foreign_keys()

    _alter_to_string("learning_records", "user_id")
    _alter_to_string("question_feedback", "user_id")
    _alter_to_string("users", "id")

    _create_user_foreign_keys()
