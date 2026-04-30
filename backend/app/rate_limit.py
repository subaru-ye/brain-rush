from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from fastapi import Depends, Request

from .config import Settings, get_settings
from .errors import ApiHttpError
from .observability import log_event


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    count: int
    reset_after_seconds: int


class FixedWindowRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[float, int]] = {}

    def check(self, key: str, *, max_requests: int, window_seconds: int) -> RateLimitResult:
        if max_requests <= 0 or window_seconds <= 0:
            return RateLimitResult(allowed=True, count=0, reset_after_seconds=0)

        now = time.monotonic()
        with self._lock:
            window_start, count = self._windows.get(key, (now, 0))
            elapsed = now - window_start
            if elapsed >= window_seconds:
                window_start = now
                count = 0

            reset_after_seconds = max(1, int(window_seconds - (now - window_start)))
            if count >= max_requests:
                return RateLimitResult(
                    allowed=False,
                    count=count,
                    reset_after_seconds=reset_after_seconds,
                )

            count += 1
            self._windows[key] = (window_start, count)
            return RateLimitResult(
                allowed=True,
                count=count,
                reset_after_seconds=reset_after_seconds,
            )

    def clear(self) -> None:
        with self._lock:
            self._windows.clear()


generation_rate_limiter = FixedWindowRateLimiter()


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_generation_rate_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    client_ip = get_client_ip(request)
    result = generation_rate_limiter.check(
        f"{client_ip}:{request.url.path}",
        max_requests=settings.generation_rate_limit_max_requests,
        window_seconds=settings.generation_rate_limit_window_seconds,
    )
    if result.allowed:
        return

    log_event(
        "rate_limited",
        path=request.url.path,
        client_ip=client_ip,
        limit=settings.generation_rate_limit_max_requests,
        window_seconds=settings.generation_rate_limit_window_seconds,
        reset_after_seconds=result.reset_after_seconds,
    )
    raise ApiHttpError(
        status_code=429,
        code="rate_limited",
        detail="生成请求过于频繁，请稍后再试",
    )
