import uuid

from conftest import credentials
from fastapi.testclient import TestClient


def register(client, email="owner@example.com"):
    headers = credentials(client)
    response = client.post("/api/v1/auth/register", headers=headers,
                           json={"email": email, "password": "OwnerTest!2026", "name": "Owner"})
    assert response.status_code == 200, response.text
    headers["x-csrf-token"] = response.json()["csrf_token"]
    return headers


def test_sessions_csrf_logout_and_validation(client):
    assert client.post("/api/v1/auth/register", json={"email": "a@example.com", "password": "OwnerTest!2026", "name": "A"}).status_code == 403
    headers = register(client)
    assert client.get("/api/v1/me").json()["user"]["email"] == "owner@example.com"
    assert client.put("/api/v1/me/preferences", headers={**headers, "origin": "https://evil.example"}, json={"categories": ["Audio"]}).status_code == 403
    assert client.put("/api/v1/me/preferences", headers=headers, json={"categories": ["unknown"]}).status_code == 422
    assert client.get("/api/v1/products?limit=500").status_code == 422
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/v1/me").json()["user"] is None
    assert client.get("/api/v1/favorites").status_code == 401


def test_ownership_admin_forged_actor_and_persistence(client):
    headers = register(client)
    assert client.put("/api/v1/favorites/demo-0000", headers=headers).status_code == 200
    assert client.get("/api/v1/favorites").json()["items"][0]["id"] == "demo-0000"
    assert client.get("/api/v1/admin/overview").status_code == 403
    forged = {"id": str(uuid.uuid4()), "item_id": "demo-0000", "kind": "click",
              "surface": "test", "user_id": "someone-else"}
    assert client.post("/api/v1/events", headers=headers, json=forged).status_code == 422
    from atlasrec_api.main import app
    with TestClient(app) as other:
        register(other, "other@example.com")
        assert other.get("/api/v1/favorites").json()["items"] == []
    assert client.get("/api/v1/favorites").json()["items"][0]["id"] == "demo-0000"


def test_real_recommendations_events_and_revision_invalidation(client):
    headers = register(client)
    rec = client.get("/api/v1/recommendations").json()
    assert rec["model_version"] == "test-pop"
    assert len({p["id"] for p in rec["items"]}) == len(rec["items"])
    item = rec["items"][0]["id"]
    event = {"id": str(uuid.uuid4()), "item_id": item, "kind": "impression", "surface": "test",
             "request_id": rec["request_id"], "position": 0}
    assert client.post("/api/v1/events", headers=headers, json=event).status_code == 200
    assert client.post("/api/v1/events", headers=headers, json=event).json()["duplicate"]
    revision = client.get("/api/v1/me").json()["user"]["history_revision"]
    assert client.post("/api/v1/events", headers=headers, json={"id": str(uuid.uuid4()), "item_id": item, "kind": "dismiss", "surface": "test"}).status_code == 200
    assert client.get("/api/v1/me").json()["user"]["history_revision"] > revision
    assert item not in [p["id"] for p in client.get("/api/v1/recommendations").json()["items"]]


def test_promotion_rollback_and_failed_worker_preserves_active(client, tmp_path, monkeypatch):
    from atlasrec_api.db import Job, ModelVersion, Run, SessionLocal, User
    from atlasrec_api.lifecycle import active_bundle, promote
    from atlasrec_api.worker import train_job
    from atlasrec_ml.bundle import save_bundle
    from sqlalchemy import select
    with SessionLocal() as db:
        model, _ = active_bundle(db)
        path = tmp_path / "second"
        save_bundle(model, path, {"version": "second", "profile": "demo"})
        db.add(Run(id="second", dataset_id="test-data", profile="demo", status="completed", record={}))
        db.flush()
        db.add(ModelVersion(id="second", run_id="second", profile="demo", path=str(path), validated=True, active=False))
        db.commit()
        admin = db.scalar(select(User).where(User.admin.is_(True)))
        promote(db, "second", admin.id)
        assert active_bundle(db)[1] == "second"
        promote(db, "test-pop", admin.id, "rollback")
        job_id = str(uuid.uuid4())
        db.add(Job(id=job_id, user_id=admin.id, config={"models": ["bpr"]}, status="queued", progress=0))
        db.commit()
    def fail(*args, **kwargs):
        raise RuntimeError("deliberate failure fixture")
    monkeypatch.setattr("atlasrec_api.worker.run", fail)
    assert train_job.run(job_id)["status"] == "failed"
    with SessionLocal() as db:
        assert active_bundle(db)[1] == "test-pop"
        assert db.get(Job, job_id).error == "deliberate failure fixture"

def test_experiment_summaries_keep_metrics_and_full_results(client):
    from atlasrec_api.db import Run, SessionLocal

    headers = register(client, "summary-owner@example.com")
    assert client.get("/api/v1/admin/experiments").status_code == 403
    assert client.get("/api/v1/admin/experiments?include_user_rows=true").status_code == 403
    with SessionLocal() as db:
        row = db.get(Run, "test-pop")
        rows = [{"user": str(index), "ranked_items": ["demo-0000"] * 10} for index in range(5000)]
        row.record = {**row.record,
                      "metrics": {"ndcg@10": 0.5, "ci95": {"ndcg@10": [0.4, 0.6]}, "user_rows": rows},
                      "validation": {"ndcg@10": 0.4, "user_rows": rows},
                      "diversity_metrics": {"category_diversity": 0.8, "user_rows": rows}}
        db.commit()
    logged_in = client.post("/api/v1/auth/login", headers=headers,
                            json={"email": "admin@atlasrec.local", "password": "AtlasDemo!2026"})
    assert logged_in.status_code == 200
    summary = client.get("/api/v1/admin/experiments")
    assert summary.status_code == 200 and len(summary.content) < 5000
    record = next(row for row in summary.json() if row["id"] == "test-pop")
    assert record["metrics"] == {"ndcg@10": 0.5, "ci95": {"ndcg@10": [0.4, 0.6]}}
    assert record["validation"] == {"ndcg@10": 0.4}
    assert record["diversity_metrics"] == {"category_diversity": 0.8}
    full = client.get("/api/v1/admin/experiments?include_user_rows=true")
    assert len(full.json()[0]["metrics"]["user_rows"]) == 5000
    with SessionLocal() as db:
        assert len(db.get(Run, "test-pop").record["metrics"]["user_rows"]) == 5000
