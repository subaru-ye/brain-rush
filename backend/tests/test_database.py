from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_alembic_current_schema_revision_is_registered():
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["0001_current_schema"]


def test_alembic_current_schema_revision_mentions_tracked_tables():
    revision_file = BACKEND_ROOT / "alembic" / "versions" / "0001_current_schema.py"
    revision_source = revision_file.read_text(encoding="utf-8")

    assert '"users"' in revision_source
    assert '"learning_records"' in revision_source
    assert '"question_feedback"' in revision_source
    assert '"quiz_prompt_version"' in revision_source
    assert '"report_model_name"' in revision_source
