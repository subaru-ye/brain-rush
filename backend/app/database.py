from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings
from .prompts import QUIZ_PROMPT_VERSION, REPORT_PROMPT_VERSION


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_learning_record_version_columns(engine)


def ensure_learning_record_version_columns(target_engine: Engine) -> None:
    inspector = inspect(target_engine)
    if "learning_records" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("learning_records")
    }
    column_specs = {
        "quiz_prompt_version": f"VARCHAR(40) NOT NULL DEFAULT '{QUIZ_PROMPT_VERSION}'",
        "quiz_model_name": "VARCHAR(120) NOT NULL DEFAULT ''",
        "report_prompt_version": f"VARCHAR(40) NOT NULL DEFAULT '{REPORT_PROMPT_VERSION}'",
        "report_model_name": "VARCHAR(120) NOT NULL DEFAULT ''",
    }

    with target_engine.begin() as connection:
        for column_name, column_spec in column_specs.items():
            if column_name not in existing_columns:
                connection.execute(
                    text(f"ALTER TABLE learning_records ADD COLUMN {column_name} {column_spec}")
                )
