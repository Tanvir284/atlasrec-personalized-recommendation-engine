"""Tests for the hardening pass: shared rate limiting, lock-free model reads, narrow queries."""
import threading

import pytest
import redis


class FakeRedis:
    """Just enough of redis-py's sorted-set API for the rate limiter."""

    def __init__(self):
        self.sets = {}

    def pipeline(self):
        return FakePipeline(self)

    def zrem(self, key, member):
        self.sets.get(key, {}).pop(member, None)

    def scan_iter(self, pattern):
        prefix = pattern.rstrip("*")
        return [key for key in list(self.sets) if key.startswith(prefix)]

    def delete(self, key):
        self.sets.pop(key, None)


class FakePipeline:
    def __init__(self, store):
        self.store, self.ops = store, []

    def zremrangebyscore(self, key, low, high):
        self.ops.append(lambda: [self.store.sets.setdefault(key, {}).pop(m) for m, s in
                                 list(self.store.sets.get(key, {}).items()) if low <= s <= high])

    def zcard(self, key):
        self.ops.append(lambda: len(self.store.sets.get(key, {})))

    def zadd(self, key, mapping):
        self.ops.append(lambda: self.store.sets.setdefault(key, {}).update(mapping))

    def expire(self, key, seconds):
        self.ops.append(lambda: True)

    def execute(self):
        return [op() for op in self.ops]


class BrokenRedis:
    def pipeline(self):
        raise redis.ConnectionError("down")

    def scan_iter(self, pattern):
        raise redis.ConnectionError("down")


class FakeRequest:
    def __init__(self, host):
        self.client = type("Client", (), {"host": host})()


@pytest.fixture
def limiter(monkeypatch):
    from atlasrec_api import cache, ratelimit
    store = FakeRedis()
    monkeypatch.setattr(cache, "client", store)
    ratelimit.local_attempts.clear()
    return ratelimit, store


def test_rate_limit_is_shared_through_the_store(limiter):
    from fastapi import HTTPException
    ratelimit, store = limiter
    for _ in range(ratelimit.AUTH_ATTEMPTS):
        ratelimit.auth_limit(FakeRequest("10.0.0.1"))
    with pytest.raises(HTTPException) as blocked:
        ratelimit.auth_limit(FakeRequest("10.0.0.1"))
    assert blocked.value.status_code == 429
    # Rejected attempts do not consume budget; another client is unaffected.
    assert len(store.sets[ratelimit.KEY_PREFIX + "10.0.0.1"]) == ratelimit.AUTH_ATTEMPTS
    ratelimit.auth_limit(FakeRequest("10.0.0.2"))
    # No per-process state was used while the store was healthy.
    assert not ratelimit.local_attempts
    ratelimit.reset()
    assert not store.sets


def test_rate_limit_falls_back_to_process_memory_when_store_is_down(monkeypatch):
    from atlasrec_api import cache, ratelimit
    from atlasrec_api.monitoring import observed_errors
    from fastapi import HTTPException
    monkeypatch.setattr(cache, "client", BrokenRedis())
    ratelimit.local_attempts.clear()
    before = observed_errors["rate_limit_store_unavailable"]
    for _ in range(ratelimit.AUTH_ATTEMPTS):
        ratelimit.auth_limit(FakeRequest("10.0.0.3"))
    with pytest.raises(HTTPException):
        ratelimit.auth_limit(FakeRequest("10.0.0.3"))
    assert observed_errors["rate_limit_store_unavailable"] > before
    ratelimit.reset()  # Must not raise while the store is down.


def test_login_endpoint_enforces_limit(client, monkeypatch):
    from atlasrec_api import cache, ratelimit
    from conftest import credentials
    monkeypatch.setattr(cache, "client", FakeRedis())
    headers = credentials(client)
    body = {"email": "nobody@example.com", "password": "WrongPassword!1"}
    statuses = [client.post("/api/v1/auth/login", headers=headers, json=body).status_code
                for _ in range(ratelimit.AUTH_ATTEMPTS + 1)]
    assert statuses[:-1] == [401] * ratelimit.AUTH_ATTEMPTS
    assert statuses[-1] == 429


def test_active_bundle_reads_do_not_take_the_load_lock(client):
    from atlasrec_api import lifecycle
    from atlasrec_api.db import SessionLocal
    with SessionLocal() as db:
        model, version = lifecycle.active_bundle(db)
    assert model is not None and version == "test-pop"
    results = []

    def read():
        with SessionLocal() as db:
            results.append(lifecycle.active_bundle(db))

    # Hold the loader lock from another thread: a warm read must still complete.
    acquired, release = threading.Event(), threading.Event()

    def hold():
        with lifecycle.bundle_lock:
            acquired.set()
            release.wait(5)

    holder = threading.Thread(target=hold)
    holder.start()
    acquired.wait(5)
    reader = threading.Thread(target=read)
    reader.start()
    reader.join(3)
    finished = not reader.is_alive()
    release.set()
    holder.join()
    reader.join()
    assert finished, "warm active_bundle() blocked on the loader lock"
    assert results == [(model, version)]


def test_reset_serving_cache_forces_reload(client):
    from atlasrec_api import lifecycle
    from atlasrec_api.db import SessionLocal
    with SessionLocal() as db:
        first, _ = lifecycle.active_bundle(db)
        lifecycle.reset_serving_cache()
        second, version = lifecycle.active_bundle(db)
    assert version == "test-pop"
    assert first is not second


def test_recommendations_hydrate_only_returned_items(client):
    from conftest import credentials
    credentials(client)
    body = client.get("/api/v1/recommendations?limit=5").json()
    assert len(body["items"]) == 5
    assert len({item["id"] for item in body["items"]}) == 5
    for item in body["items"]:
        assert {"id", "title", "description", "category", "price", "image", "available", "reason"} <= item.keys()
        assert item["available"] is True


def _entries(spec):
    from atlasrec_api.routers.recommendations import _Entry, _title_key
    return {item: _Entry("Beauty", _title_key(title), photo) for item, title, photo in spec}


def test_select_collapses_title_variants_and_prefers_photos_when_cold():
    from atlasrec_api.routers.recommendations import _select
    catalog = _entries([("a", "Nail Polish", False), ("b", "nail  polish", True),
                        ("c", "Shampoo", False), ("d", "Conditioner", True)])
    chosen, duplicates = _select(["a", "b", "c", "d"], catalog, set(), 3, prefer_photos=False)
    assert chosen == ["a", "c", "d"] and duplicates == ["b"]
    chosen, _ = _select(["a", "b", "c", "d"], catalog, set(), 3, prefer_photos=True)
    assert chosen == ["b", "d", "c"]  # photographed first, model order kept within each group


def test_backfill_uses_repeated_titles_only_as_last_resort():
    from atlasrec_api.routers.recommendations import _backfill
    catalog = _entries([("a", "Lamp", True), ("b", "Lamp", True), ("c", "Desk", False), ("d", "Desk", True)])
    ids = []
    _backfill(ids, catalog, {"x"}, [], None, 2)
    assert ids == ["a", "d"]  # distinct titles, photo before no photo
    ids = []
    _backfill(ids, catalog, set(), [], None, 4)
    assert sorted(ids) == ["a", "b", "c", "d"] and len(set(ids)) == 4


def test_router_split_preserves_the_public_api():
    from atlasrec_api.main import app
    paths = app.openapi()["paths"]
    expected = {
        "/health/live": {"get"}, "/health/ready": {"get"},
        "/api/v1/auth/csrf": {"get"}, "/api/v1/auth/register": {"post"},
        "/api/v1/auth/login": {"post"}, "/api/v1/auth/logout": {"post"},
        "/api/v1/me": {"get", "patch", "delete"},
        "/api/v1/me/password": {"post"},
        "/api/v1/me/sessions": {"get"},
        "/api/v1/me/sessions/{session_id}": {"delete"},
        "/api/v1/me/preferences": {"put"},
        "/api/v1/me/history": {"get", "delete"},
        "/api/v1/me/history/{event_id}": {"delete"},
        "/api/v1/favorites": {"get"},
        "/api/v1/favorites/{item_id}": {"put", "delete"},
        "/api/v1/categories": {"get"}, "/api/v1/catalog/info": {"get"},
        "/api/v1/products": {"get"}, "/api/v1/products/{item_id}": {"get"},
        "/api/v1/events": {"post"}, "/api/v1/recommendations": {"get"},
        "/api/v1/admin/overview": {"get"},
        "/api/v1/admin/users": {"get", "post"},
        "/api/v1/admin/users/{user_id}": {"patch", "delete"},
        "/api/v1/admin/users/{user_id}/history": {"delete"},
        "/api/v1/admin/datasets": {"get"},
        "/api/v1/admin/experiments": {"get"}, "/api/v1/admin/models": {"get"},
        "/api/v1/admin/models/{version}/promote": {"post"},
        "/api/v1/admin/models/rollback": {"post"},
        "/api/v1/admin/jobs": {"get", "post"}, "/api/v1/admin/jobs/{job_id}/retry": {"post"},
        "/api/v1/admin/monitoring": {"get"},
    }
    assert {path: set(methods) for path, methods in paths.items()} == expected

