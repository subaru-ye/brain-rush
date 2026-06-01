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


def get_optional_user_id(
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> str | None:
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        return None
    try:
        return decode_auth_token(authorization.removeprefix("Bearer ").strip(), settings)
    except ApiHttpError:
        return None


def require_admin_token(
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    expected_token = settings.admin_api_token.strip()
    if not expected_token:
        raise ApiHttpError(404, "admin_disabled", "管理接口未启用")
    if not x_admin_token or x_admin_token.strip() != expected_token:
        raise ApiHttpError(401, "admin_auth_invalid", "管理接口令牌无效")


def require_debug_rag_access(
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    if settings.app_env.strip().lower() == "development":
        return

    expected_token = settings.admin_api_token.strip()
    if not expected_token:
        raise ApiHttpError(404, "admin_disabled", "管理接口未启用")
    if not x_admin_token or x_admin_token.strip() != expected_token:
        raise ApiHttpError(401, "admin_auth_invalid", "管理接口令牌无效")
