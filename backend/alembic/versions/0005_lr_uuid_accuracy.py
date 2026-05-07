from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_lr_uuid_accuracy"
down_revision = "0004_user_uuid_ids"
branch_labels = None
depends_on = None


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


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql" or not _table_exists("learning_records"):
        return

    columns = _column_names("learning_records")
    if "id" in columns and _column_type_name("learning_records", "id") != "uuid":
        op.alter_column(
            "learning_records",
            "id",
            existing_type=sa.String(length=32),
            type_=sa.Uuid(as_uuid=False),
            postgresql_using="id::uuid",
        )
    if "score" in columns:
        op.drop_column("learning_records", "score")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql" or not _table_exists("learning_records"):
        return

    columns = _column_names("learning_records")
    if "score" not in columns:
        op.add_column(
            "learning_records",
            sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        )
        op.execute("update learning_records set score = accuracy_percent")
        op.alter_column("learning_records", "score", server_default=None)
    if "id" in columns and _column_type_name("learning_records", "id") == "uuid":
        op.alter_column(
            "learning_records",
            "id",
            existing_type=sa.Uuid(as_uuid=False),
            type_=sa.String(length=32),
            postgresql_using="replace(id::text, '-', '')",
        )
