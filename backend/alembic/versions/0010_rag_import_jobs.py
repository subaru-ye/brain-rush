from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_rag_import_jobs"
down_revision = "0009_keyword_fts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rag_import_jobs",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("source_type", sa.String(length=40), nullable=False, server_default="upload"),
        sa.Column("source_uri", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("file_name", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("collection_title", sa.String(length=120), nullable=False),
        sa.Column("document_title", sa.String(length=180), nullable=True),
        sa.Column("chunk_size", sa.Integer(), nullable=False, server_default="1200"),
        sa.Column("chunk_overlap", sa.Integer(), nullable=False, server_default="150"),
        sa.Column("stats_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("queue_job_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_rag_import_jobs_status_created",
        "rag_import_jobs",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_rag_import_jobs_status_created", table_name="rag_import_jobs")
    op.drop_table("rag_import_jobs")
