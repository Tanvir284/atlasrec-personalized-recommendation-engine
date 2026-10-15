import uuid

from conftest import credentials
from fastapi.testclient import TestClient
from test_api import register


def test_anonymous_exposure_ownership_and_rating_validation(client):
    headers = credentials(client)
    rec = client.get("/api/v1/recommendations").json()
    item = rec["items"][0]["id"]
    impression = {"id": str(uuid.uuid4()), "item_id": item, "kind": "impression",
                  "surface": "test", "request_id": rec["request_id"], "position": 0}
    from atlasrec_api.main import app
    with TestClient(app) as other:
        protection = credentials(other)
        assert other.post("/api/v1/events", headers=protection, json=impression).status_code == 403
    assert client.post("/api/v1/events", headers=headers, json=impression).status_code == 200
    assert client.post("/api/v1/events", headers=headers, json={**impression, "id": str(uuid.uuid4())}).json()["duplicate"]
    headers = register(client, "ratings@example.com")
    rating = {"id": str(uuid.uuid4()), "item_id": item, "kind": "rating", "surface": "test"}
    assert client.post("/api/v1/events", headers=headers, json=rating).status_code == 422
    assert client.post("/api/v1/events", headers=headers, json={**rating, "rating": 6}).status_code == 422
    rating["rating"] = 1
    assert client.post("/api/v1/events", headers=headers, json=rating).status_code == 200
    assert client.post("/api/v1/events", headers=headers, json=rating).json()["duplicate"]
    assert client.post("/api/v1/events", headers=headers, json={**rating, "rating": 5}).status_code == 409
    assert item not in [p["id"] for p in client.get("/api/v1/recommendations").json()["items"]]


def test_product_rating_survives_busy_history_and_stays_private(client):
    from datetime import datetime, timedelta, timezone

    from atlasrec_api.db import Event, SessionLocal
    from atlasrec_api.main import app

    headers = register(client, "rating-history@example.com")
    owner = client.get("/api/v1/me").json()["user"]["id"]
    rating = {"id": str(uuid.uuid4()), "item_id": "demo-0000", "kind": "rating",
              "surface": "product-detail", "rating": 4}
    assert client.post("/api/v1/events", headers=headers, json=rating).status_code == 200
    base = datetime.now(timezone.utc)
    with SessionLocal() as db:
        db.add_all([Event(id=str(uuid.uuid4()), user_id=owner, item_id="demo-0001",
                          kind="view", surface="test", profile="demo",
                          created_at=base + timedelta(seconds=index))
                    for index in range(110)])
        db.commit()
    history = client.get("/api/v1/me/history").json()
    assert len(history) == 100
    assert not any(event["kind"] == "rating" for event in history)
    path = "/api/v1/me/history?ratings_only=true&item_id=demo-0000"
    personal = client.get(path).json()
    assert len(personal) == 1 and personal[0]["rating"] == 4
    assert client.get("/api/v1/me/history?ratings_only=true&item_id=demo-0001").json() == []
    with TestClient(app) as other:
        protection = register(other, "rating-other@example.com")
        assert other.get(path).json() == []
        assert other.post("/api/v1/events", headers=protection,
                          json={**rating, "id": str(uuid.uuid4()), "rating": 1}).status_code == 200
    assert client.get(path).json()[0]["rating"] == 4
