"""Shared Redis client.

Routers access ``cache.client`` at call time (not ``from .cache import client``) so tests
can substitute the client with ``monkeypatch.setattr(cache, "client", fake)``.
"""
import redis

from .settings import settings

client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=0.2,
                              socket_timeout=0.2, decode_responses=True)
