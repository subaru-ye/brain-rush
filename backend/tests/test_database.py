from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_alembic_current_schema_revision_is_registered():
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["0008_knowledge_documents"]


def test_alembic_current_schema_revision_mentions_tracked_tables():
    revision_file = BACKEND_ROOT / "alembic" / "versions" / "0008_knowledge_documents.py"
    revision_source = revision_file.read_text(encoding="utf-8")

    assert '"knowledge_documents"' in revision_source
    assert '"knowledge_chunks"' in revision_source
    assert '"document_id"' in revision_source
