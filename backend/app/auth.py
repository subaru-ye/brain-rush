from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, Header
from jwt import ExpiredSignatureError, InvalidTokenError

from .config import Settings, get_settings
from .errors import ApiHttpError

JWT_ALGORITHM = "HS256"


def create_auth_token(user_id: str, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(days=settings.auth_token_expire_days),
    }
    return jwt.encode(payload, settings.auth_token_secret, algorithm=JWT_ALGORITHM)


def decode_auth_token(token: str, settings: Settings) -> str:
    try:
        payload = jwt.decode(token, settings.auth_token_secret, algorithms=[JWT_ALGORITHM])
    except ExpiredSignatureError as exc:
        raise ApiHttpError(401, "auth_expired", "登录状态已过期，请重新进入小程序") from exc
    except InvalidTokenError as exc:
        raise ApiHttpError(401, "auth_invalid", "登录状态无效，请重新进入小程序") from exc

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise ApiHttpError(401, "auth_invalid", "登录状态无效，请重新进入小程序")
    return user_id


def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise ApiHttpError(401, "auth_required", "请先完成登录")

    return decode_auth_token(authorization.removeprefix("Bearer ").strip(), settings)
