"""Lightweight async cache helpers backed by Redis."""

from __future__ import annotations

import json
from typing import Any

from app.core.redis_client import get_redis


async def cache_get(key: str) -> Any | None:
    redis = get_redis()
    try:
        raw = await redis.get(key)
    except Exception:
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


async def cache_set(key: str, value: Any, ttl: int = 60) -> None:
    redis = get_redis()
    try:
        await redis.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:
        pass


async def cache_delete(*keys: str) -> None:
    if not keys:
        return
    redis = get_redis()
    try:
        await redis.delete(*keys)
    except Exception:
        pass


async def cache_delete_prefix(prefix: str) -> None:
    """Delete all keys starting with prefix (e.g. trends:)."""
    redis = get_redis()
    try:
        keys: list[str] = []
        async for key in redis.scan_iter(f"{prefix}*"):
            keys.append(key)
            if len(keys) >= 200:
                await redis.delete(*keys)
                keys = []
        if keys:
            await redis.delete(*keys)
    except Exception:
        pass
