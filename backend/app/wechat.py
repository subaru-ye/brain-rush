from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import httpx

from .config import Settings
from .errors import ApiHttpError

WECHAT_CODE2SESSION_URL = "https://api.weixin.qq.com/sns/jscode2session"


@dataclass(frozen=True)
class WechatSession:
    openid: str
    unionid: str | None = None


async def exchange_wechat_code(code: str, settings: Settings) -> WechatSession:
    if not settings.wechat_appid or not settings.wechat_secret:
        if settings.app_env != "production":
            digest = sha256(code.encode("utf-8")).hexdigest()[:24]
            return WechatSession(openid=f"dev_{digest}")
        raise ApiHttpError(500, "wechat_config_missing", "微信登录配置缺失")

    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.get(
            WECHAT_CODE2SESSION_URL,
            params={
                "appid": settings.wechat_appid,
                "secret": settings.wechat_secret,
                "js_code": code,
                "grant_type": "authorization_code",
            },
        )

    if response.status_code >= 400:
        raise ApiHttpError(502, "wechat_upstream_error", "微信登录服务暂时不可用")

    data = response.json()
    openid = data.get("openid")
    if not isinstance(openid, str) or not openid:
        raise ApiHttpError(401, "wechat_login_failed", "微信登录失败，请稍后重试")

    unionid = data.get("unionid")
    return WechatSession(openid=openid, unionid=unionid if isinstance(unionid, str) else None)
