import json
import uuid
from concurrent.futures import ThreadPoolExecutor

from conftest import credentials
from fastapi.testclient import TestClient
from test_api import register


def feedback(client, headers, item="demo-0000", kind="rating", **values):
    return client.post("/api/v1/events", headers=headers, json={
        "id": str(uuid.uuid4()), "item_id": item, "kind": kind,
        "surface": "audit", **values,
    })


def test_latest_explicit_feedback_and_views(client):
    from atlasrec_api.db import SessionLocal, User
    from atlasrec_api.main import allowed_history
    from sqlalchemy import select

    headers = register(client)
    assert feedback(client, headers, rating=1).status_code == 200
    assert feedback(client, headers, rating=5).status_code == 200
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "owner@example.com"))
        history, dismissed = allowed_history(db, user)
        assert "demo-0000" in history
        assert "demo-0000" not in dismissed
    assert feedback(client, headers, rating=3).status_code == 200
    with SessionLocal() as db:
        assert allowed_history(db, db.get(User, user.id)) == ([], [])
    revision = client.get("/api/v1/me").json()["user"]["history_revision"]
    assert feedback(client, headers, item="demo-0001", kind="view").status_code == 200
    assert client.get("/api/v1/me").json()["user"]["history_revision"] == revision + 1
    assert feedback(client, headers, item="demo-0001", kind="dismiss").status_code == 200
    assert feedback(client, headers, item="demo-0001", kind="view").status_code == 200
    with SessionLocal() as db:
        assert allowed_history(db, db.get(User, user.id)) == ([], ["demo-0001"])


def test_changed_rating_on_one_served_request_and_identity(client):
    headers = register(client)
    rec = client.get("/api/v1/recommendations").json()
    item = rec["items"][0]["id"]
    first = feedback(client, headers, item, request_id=rec["request_id"], position=0, rating=1)
    second = feedback(client, headers, item, request_id=rec["request_id"], position=0, rating=3)
    assert first.status_code == second.status_code == 200
    assert not second.json()["duplicate"]
    assert feedback(client, headers, item, kind="click", request_id=str(uuid.uuid4())).status_code == 422
    assert feedback(client, headers, item, kind="click", position=0).status_code == 422
    payload = {"id": str(uuid.uuid4()), "item_id": item, "kind": "click", "surface": "audit",
               "request_id": rec["request_id"], "position": 0}
    assert client.post("/api/v1/events", headers=headers, json=payload).status_code == 200
    assert client.post("/api/v1/events", headers=headers, json={**payload, "position": 1}).status_code == 409


def test_csrf_cookie_recovery_preserves_session(client):
    headers = register(client)
    client.cookies.delete("atlas_csrf")
    headers["x-csrf-token"] = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    response = client.put("/api/v1/me/preferences", headers=headers, json={"categories": ["Audio"]})
    assert response.status_code == 200, response.text
    assert client.get("/api/v1/me").json()["user"]["email"] == "owner@example.com"
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200


def test_corrupt_and_stale_cache_and_inference_failure(client, monkeypatch):
    from atlasrec_api import cache as cache_store
    from atlasrec_api import main
    from atlasrec_api.db import Product, RecommendationRequest, SessionLocal

    class Cache:
        value = None
        def get(self, key):
            return self.value
        def set(self, key, value, ex):
            self.value = value
    cache = Cache()
    monkeypatch.setattr(cache_store, "client", cache)
    credentials(client)
    for corrupt in ("{broken", "null", json.dumps({"ids": [12], "fallback": None})):
        cache.value = corrupt
        response = client.get("/api/v1/recommendations")
        assert response.status_code == 200, response.text
        assert len(response.json()["items"]) == 12
    initial = client.get("/api/v1/recommendations").json()
    removed = initial["items"][0]["id"]
    with SessionLocal() as db:
        db.get(Product, removed).available = False
        db.commit()
    refreshed = client.get("/api/v1/recommendations").json()
    assert len(refreshed["items"]) == 12
    assert removed not in [p["id"] for p in refreshed["items"]]
    with SessionLocal() as db:
        assert db.get(RecommendationRequest, refreshed["request_id"]).item_ids == [p["id"] for p in refreshed["items"]]
    model, version = main.active_bundle(next_db := SessionLocal())
    next_db.close()
    def fail(*args, **kwargs):
        raise RuntimeError("audit inference failure")
    monkeypatch.setattr(model, "recommend", fail)
    cache.value = None
    result = client.get("/api/v1/recommendations").json()
    assert result["fallback"] == "model_inference_failed"
    assert result["model_version"] == version and len(result["items"]) == 12


def test_concurrent_favorites_and_revision(client):
    from atlasrec_api.db import Event, Favorite, SessionLocal
    from atlasrec_api.main import app
    from sqlalchemy import func, select

    headers = register(client)
    cookie_values = dict(client.cookies)
    def save(item):
        with TestClient(app) as other:
            other.cookies.update(cookie_values)
            return other.put("/api/v1/favorites/" + item, headers=headers).status_code
    with ThreadPoolExecutor(max_workers=5) as pool:
        statuses = list(pool.map(save, ["demo-0000"] * 3 + ["demo-0001", "demo-0002"]))
    assert statuses == [200] * 5
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Favorite)) == 3
        assert db.scalar(select(func.count()).select_from(Event).where(Event.kind == "favorite")) == 3
    assert client.get("/api/v1/me").json()["user"]["history_revision"] == 3


def test_registration_and_literal_search_validation(client):
    from atlasrec_api.db import Product, SessionLocal
    headers = credentials(client)
    for email, name in [("bad@@example.com", "Owner"), ("bad name@example.com", "Owner"), ("ok@example.com", "   ")]:
        result = client.post("/api/v1/auth/register", headers=headers, json={
            "email": email, "name": name, "password": "OwnerTest!2026"})
        assert result.status_code == 422
    with SessionLocal() as db:
        db.get(Product, "demo-0000").title = r"Desk 100% A_B\\C"
        db.commit()
    for query in (r"\\C", "100%", "A_B"):
        response = client.get("/api/v1/products", params={"q": query})
        assert [p["id"] for p in response.json()["items"]] == ["demo-0000"]
    assert client.get("/api/v1/products?min_price=20&max_price=10").status_code == 422


def test_minimal_content_features():
    from atlasrec_ml.models import Recommender
    products = [{"id": "a", "title": "same", "category": ""}, {"id": "b", "title": "same", "category": ""}]
    events = [{"id": str(i), "user": "u", "item": p["id"], "timestamp": i, "rating": 5} for i, p in enumerate(products)]
    model = Recommender().fit(products, events)
    assert len(model.recommend(k=2)[0]) == 2
    assert model.embed_product({"id": "new", "title": "same", "category": ""}).shape == model.item_vectors[0].shape


def test_idempotent_promotion_and_profile_safe_rollback(client):
    from atlasrec_api.db import Audit, SessionLocal, User
    from sqlalchemy import func, select
    headers = credentials(client)
    response = client.post("/api/v1/auth/login", headers=headers, json={
        "email": "admin@atlasrec.local", "password": "AtlasDemo!2026"})
    assert response.status_code == 200
    headers["x-csrf-token"] = response.json()["csrf_token"]
    with SessionLocal() as db:
        before = db.scalar(select(func.count()).select_from(Audit))
    assert client.post("/api/v1/admin/models/test-pop/promote", headers=headers).status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Audit)) == before
        admin = db.scalar(select(User).where(User.admin.is_(True)))
        db.add(Audit(id=str(uuid.uuid4()), actor_id=admin.id, action="promote",
                     details={"profile": "research", "previous": ["foreign-version"], "next": "foreign-next"}))
        db.commit()
    result = client.post("/api/v1/admin/models/rollback", headers=headers)
    assert result.status_code == 422, result.text


def test_research_import_rejects_non_objects_and_normalizes_metadata(tmp_path):
    from atlasrec_ml.data import research
    reviews = tmp_path / "reviews.jsonl"
    rows = [{"user_id": "reviewer", "parent_asin": "parent", "timestamp": (1700000000+i)*1000,
             "rating": 4} for i in range(120)]
    rows.extend([[], 123, {"user_id": 123, "parent_asin": "parent", "timestamp": 1700000000000, "rating": 4}])
    reviews.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    metadata = tmp_path / "metadata.jsonl"
    metadata.write_text("\n".join(json.dumps(row) for row in [
        [], {"parent_asin": "parent", "title": "Title", "description": "Actual words", "price": "NaN"}]), encoding="utf-8")
    data = research({"reviews_path": str(reviews), "metadata_path": str(metadata), "category": "test",
                     "source_url": "fixture", "terms_url": "fixture", "user_sample_fraction": 1})
    assert data.manifest["rejected"] == 3
    assert data.manifest["meta_rejected"] == 1
    assert data.products[0]["description"] == "Actual words"
    assert data.products[0]["price"] is None


def test_demo_identity_changes_with_user_population():
    from atlasrec_ml.data import demo
    a = demo(products=10, users=10, interactions=100)
    b = demo(products=10, users=11, interactions=100)
    assert a.events != b.events
    assert a.manifest["dataset_id"] != b.manifest["dataset_id"]


def test_similar_to_preserves_user_seen_exclusions_and_profile_scoped_clear_history(client):
    from atlasrec_api.db import Event, Favorite, Product, SessionLocal, User
    from atlasrec_api.ratelimit import _client_key
    from sqlalchemy import select

    headers = register(client, "scoped-owner@example.com")
    assert feedback(client, headers, item="demo-0001", kind="view").status_code == 200
    assert client.put("/api/v1/favorites/demo-0002", headers=headers).status_code == 200

    rec = client.get("/api/v1/recommendations", params={"similar_to": "demo-0000", "limit": 30}).json()
    served_ids = {item["id"] for item in rec["items"]}
    assert "demo-0000" not in served_ids
    assert "demo-0001" not in served_ids
    assert "demo-0002" not in served_ids

    hist = client.get("/api/v1/me/history").json()
    assert hist and hist[0]["title"] is not None

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "scoped-owner@example.com"))
        db.add(Product(id="research-item-1", title="Research GPU", category="GPUs",
                       description="Desc", price=499.0, currency="USD", image="",
                       profile="research", available=True))
        db.flush()
        db.add(Favorite(user_id=user.id, item_id="research-item-1"))
        db.add(Event(id=str(uuid.uuid4()), user_id=user.id, actor_key="u:" + user.id,
                     item_id="research-item-1", kind="favorite", surface="saved", profile="research"))
        db.commit()

    assert client.delete("/api/v1/me/history", headers=headers).status_code == 200
    assert client.get("/api/v1/favorites").json()["items"] == []
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "scoped-owner@example.com"))
        remaining_favs = db.scalars(select(Favorite.item_id).where(Favorite.user_id == user.id)).all()
        remaining_events = db.scalars(select(Event.item_id).where(Event.user_id == user.id)).all()
        assert remaining_favs == ["research-item-1"]
        assert remaining_events == ["research-item-1"]

    class DummyProxyRequest:
        headers = {"x-forwarded-for": "203.0.113.9, 10.0.0.1"}
        client = None

    assert _client_key(DummyProxyRequest()) == "203.0.113.9"


def test_taste_studio_counterfactual_bundle_and_lanes(client):
    headers = register(client, "studio-owner@example.com")
    assert feedback(client, headers, item="demo-0001", kind="view").status_code == 200
    assert client.put("/api/v1/favorites/demo-0002", headers=headers).status_code == 200

    res = client.get(
        "/api/v1/recommendations",
        params={
            "limit": 10,
            "intent": "hidden_gems",
            "diversity": 0.25,
            "max_price": 80,
            "ignore_items": "demo-0001",
            "include_bundle": "true",
            "include_lanes": "true",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["studio"]["intent"] == "hidden_gems"
    assert body["studio"]["ignored_count"] == 1
    assert any(s["id"] == "demo-0001" and s["muted"] is True for s in body["active_seeds"])
    assert all(item["price"] <= 80 for item in body["items"])
    assert all(72 <= item["match_pct"] <= 99 for item in body["items"])
    assert all("taste_similarity" in item["score_breakdown"] for item in body["items"])
    assert body["bundle"] is not None
    assert len(body["bundle"]["items"]) >= 2
    assert len({item["category"] for item in body["bundle"]["items"]}) >= 2
    assert len(body["lanes"]) >= 2


