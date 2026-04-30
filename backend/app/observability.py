from __future__ import annotations

import contextvars
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any


REQUEST_ID_HEADER = "X-Request-ID"

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
logger = logging.getLogger("brain_rush")


def configure_logging() -> None:
    """Configure one JSON log handler for the API process."""

    if logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def new_request_id() -> str:
    return uuid.uuid4().hex


def get_request_id() -> str:
    return _request_id.get()


def set_request_id(request_id: str) -> contextvars.Token[str]:
    return _request_id.set(request_id)


def reset_request_id(token: contextvars.Token[str]) -> None:
    _request_id.reset(token)


def log_event(
    event: str,
    *,
    level: int = logging.INFO,
    exc_info: bool = False,
    **fields: Any,
) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "request_id": fields.pop("request_id", None) or get_request_id() or None,
    }
    payload.update({key: value for key, value in fields.items() if value is not None})
    logger.log(level, json.dumps(payload, ensure_ascii=False, default=str), exc_info=exc_info)
