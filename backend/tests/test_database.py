from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from app.database import ensure_learning_record_version_columns


def test_init_database_adds_missing_learning_record_version_columns():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE learning_records (
                    id VARCHAR(32) PRIMARY KEY,
                    user_id VARCHAR(32) NOT NULL,
                    session_id VARCHAR(64) NOT NULL,
                    topic VARCHAR(120) NOT NULL,
                    questions_json JSON NOT NULL,
                    answers_json JSON NOT NULL,
                    report_json JSON NOT NULL,
                    score INTEGER NOT NULL,
                    total INTEGER NOT NULL,
                    accuracy_percent INTEGER NOT NULL,
                    completed_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP NOT NULL
                )
                """
            )
        )

    ensure_learning_record_version_columns(engine)
    ensure_learning_record_version_columns(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("learning_records")}
    assert "quiz_prompt_version" in columns
    assert "quiz_model_name" in columns
    assert "report_prompt_version" in columns
    assert "report_model_name" in columns
