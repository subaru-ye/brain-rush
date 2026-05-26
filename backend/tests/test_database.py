from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_alembic_current_schema_revision_is_registered():
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["0010_rag_import_jobs"]


def test_alembic_current_schema_revision_mentions_tracked_tables():
    revision_file = BACKEND_ROOT / "alembic" / "versions" / "0010_rag_import_jobs.py"
    revision_source = revision_file.read_text(encoding="utf-8")

    assert "rag_import_jobs" in revision_source
    assert "status" in revision_source
    assert "queue_job_id" in revision_source
