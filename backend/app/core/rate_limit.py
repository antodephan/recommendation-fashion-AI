"""Redis-backed sliding-window rate limiter."""

from __future__ import annotations

import time
from typing import Callable

from fastapi import Request

from app.core.exceptions import RateLimitError
from app.core.redis_client import get_redis


def _parse(rate: str) -> tuple[int, int]:
    """Parse '<count>/<unit>' rate strings into (limit, window_seconds)."""
    count_str, unit = rate.split("/")
    count = int(count_str)
    unit = unit.strip().lower()
    seconds = {
        "second": 1, "sec": 1, "s": 1,
        "minute": 60, "min": 60, "m": 60,
        "hour": 3600, "h": 3600,
        "day": 86400, "d": 86400,
    }.get(unit, 60)
    return count, seconds


def rate_limit(rate: str, scope: str = "default") -> Callable:
    """Return a FastAPI dependency enforcing a per-IP rate limit."""
    limit, window = _parse(rate)

    async def _dependency(request: Request) -> None:
        identity = (
            request.client.host
            if request.client else "anonymous"
        )
        # Authenticated requests get a more specific key.
        user = getattr(request.state, "user_id", None)
        if user:
            identity = f"u:{user}"

        bucket = f"rl:{scope}:{identity}:{int(time.time()) // window}"
        redis = get_redis()
        try:
            current = await redis.incr(bucket)
            if current == 1:
                await redis.expire(bucket, window)
        except Exception:
            # Fail open — never block on Redis outage.
            return
        if current > limit:
            raise RateLimitError(f"Rate limit exceeded ({rate})")

    return _dependency
