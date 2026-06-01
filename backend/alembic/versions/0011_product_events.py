from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011_product_events"
down_revision = "0010_rag_import_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_events",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("client_id", sa.String(length=80), nullable=False),
        sa.Column("event_name", sa.String(length=80), nullable=False),
        sa.Column("page", sa.String(length=80), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("topic", sa.String(length=120), nullable=True),
        sa.Column("properties_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_product_events_event_created",
        "product_events",
        ["event_name", "created_at"],
    )
    op.create_index(
        "ix_product_events_client_created",
        "product_events",
        ["client_id", "created_at"],
    )
    op.create_index(
        "ix_product_events_user_created",
        "product_events",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_product_events_user_created", table_name="product_events")
    op.drop_index("ix_product_events_client_created", table_name="product_events")
    op.drop_index("ix_product_events_event_created", table_name="product_events")
    op.drop_table("product_events")
