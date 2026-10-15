"""Authentication rate limiting.

The limit is a 60-second sliding window stored in a Redis sorted set, so it is shared by
every API process and survives restarts. When Redis is unreachable, a per-process window
keeps brute-force protection active instead of failing open.
"""
from __future__ import annotations

import secrets
import time
from collections import defaultdict, deque

import redis
from fastapi import HTTPException, Request

from . import cache
from .monitoring import observed_errors

AUTH_ATTEMPTS = 15
WINDOW_SECONDS = 60
KEY_PREFIX = "atlasrec:ratelimit:auth:"
MESSAGE = "Too many authentication attempts; retry in one minute"

# Fallback store used only while Redis is unavailable.
local_attempts: defaultdict[str, deque] = defaultdict(deque)


def _client_key(request: Request) -> str:
    headers = getattr(request, "headers", None) or {}
    forwarded = headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def _local_limit(key: str) -> None:
    attempts, current = local_attempts[key], time.monotonic()
    while attempts and attempts[0] < current - WINDOW_SECONDS:
        attempts.popleft()
    if len(attempts) >= AUTH_ATTEMPTS:
        raise HTTPException(429, MESSAGE)
    attempts.append(current)


def auth_limit(request: Request) -> None:
    key = _client_key(request)
    redis_key = KEY_PREFIX + key
    current = time.time()
    member = f"{current:.6f}:{secrets.token_hex(4)}"
    try:
        pipe = cache.client.pipeline()
        pipe.zremrangebyscore(redis_key, 0, current - WINDOW_SECONDS)
        pipe.zcard(redis_key)
        pipe.zadd(redis_key, {member: current})
        pipe.expire(redis_key, WINDOW_SECONDS)
        _, count, _, _ = pipe.execute()
        if count >= AUTH_ATTEMPTS:
            # Rejected attempts do not consume budget, matching the in-process behaviour.
            cache.client.zrem(redis_key, member)
    except redis.RedisError:
        observed_errors["rate_limit_store_unavailable"] += 1
        _local_limit(key)
        return
    if count >= AUTH_ATTEMPTS:
        raise HTTPException(429, MESSAGE)


def reset() -> None:
    """Clear all counters. Intended for tests and local demo resets."""
    local_attempts.clear()
    try:
        for key in cache.client.scan_iter(KEY_PREFIX + "*"):
            cache.client.delete(key)
    except redis.RedisError:
        pass
