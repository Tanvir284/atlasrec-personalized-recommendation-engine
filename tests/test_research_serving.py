import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from conftest import credentials


def research_data():
    from atlasrec_ml.data import Dataset
    products = [{"id": f"real-{i}", "title": f"Source item {i}", "description": "A source catalog product",
                 "category": "Beauty" if i < 3 else "Skincare", "price": None, "currency": None,
                 "image": f"https://images.example.com/{i}.jpg", "available": True} for i in range(6)]
    events = [{"id": f"historical-{i}", "user": f"reviewer-{i % 3}", "item": products[i % 6]["id"],
               "rating": 5, "timestamp": 1500000000 + i * 100, "kind": "imported_review"} for i in range(30)]
    return Dataset(products, events, {"dataset_id": "research-unit-fixture", "profile": "research", "synthetic": False,
                                      "source": "https://example.com/source", "row_count": len(events)})


def install_fixture(monkeypatch, tmp_path):
    from atlasrec_api.db import SessionLocal
    from atlasrec_api.research import install_research_catalog
    from atlasrec_api.settings import settings
    monkeypatch.setattr(settings, "profile", "research")
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "research_dataset_id", "research-unit-fixture")
    with SessionLocal() as db:
        return install_research_catalog(db, research_data())


def test_catalog_install_provenance_images_and_profile_guards(client, tmp_path, monkeypatch):
    from atlasrec_api.db import Product, SessionLocal, User
    from atlasrec_api.research import install_research_catalog, load_snapshot
    from sqlalchemy import func, select
    with SessionLocal() as db:
        original_users = db.scalar(select(func.count()).select_from(User))
    manifest = install_fixture(monkeypatch, tmp_path)
    assert load_snapshot(manifest).manifest["synthetic"] is False
    result = client.get("/api/v1/products").json()
    assert len(result["items"]) == 6
    assert all(item["image"].startswith("https://") and not item["id"].startswith("demo-") for item in result["items"])
    categories = client.get("/api/v1/categories").json()
    assert len(categories) == 2 and all(len(category["preview_items"]) == 3 for category in categories)
    info = client.get("/api/v1/catalog/info").json()
    assert info["historical_reviewers"] == 3 and info["historical_interactions"] == 30
    assert info["product_count"] == 6 and info["recorded_application_events"] == 0
    assert info["personalization"]["status"] == "fallback"
    assert "reviewer-" not in json.dumps(info)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(User)) == original_users
        assert db.get(Product, "demo-0000").profile == "demo"
        invalid = research_data()
        invalid.manifest["synthetic"] = True
        with pytest.raises(ValueError, match="real research"):
            install_research_catalog(db, invalid)
    path = tmp_path / "catalog" / (manifest["dataset_id"] + ".json")
    path.write_text("{}")
    with pytest.raises(ValueError, match="checksum"):
        load_snapshot(manifest)


def test_live_feedback_snapshot_latest_private_explicit_server_time(client, tmp_path, monkeypatch):
    from atlasrec_api.db import Event, SessionLocal, User
    from atlasrec_api.research import load_snapshot, training_snapshot
    from sqlalchemy import select
    install_fixture(monkeypatch, tmp_path)
    stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.admin.is_(True)))
        user = User(id=str(uuid.uuid4()), name="Real person", email="private@example.com", password_hash="unused", admin=False)
        db.add(user)
        db.flush()
        for offset, item, kind, rating in [(0, "real-0", "rating", 5), (1, "real-0", "rating", 1),
                                           (2, "real-1", "favorite", None), (3, "real-2", "view", None),
                                           (4, "real-3", "dismiss", None), (5, "real-4", "impression", None)]:
            db.add(Event(id=str(uuid.uuid4()), user_id=user.id, item_id=item, kind=kind, rating=rating,
                         profile="research", surface="test", created_at=stamp + timedelta(seconds=offset),
                         client_timestamp=stamp - timedelta(days=1)))
        db.add(Event(id=str(uuid.uuid4()), user_id=admin.id, item_id="real-5", kind="rating", rating=5,
                     profile="research", surface="test", created_at=stamp))
        db.add(Event(id=str(uuid.uuid4()), user_id=user.id, item_id="demo-0000", kind="rating", rating=5,
                     profile="demo", surface="test", created_at=stamp))
        db.commit()
        reference = training_snapshot(db)
        snapshot = load_snapshot(reference)
        app = [event for event in snapshot.events if event["kind"].startswith("application_")]
        assert len(app) == 3
        assert {event["item"]: event["rating"] for event in app} == {"real-0": 1, "real-1": 5, "real-3": 1}
        assert all(event["user"] == "app:" + user.id for event in app)
        assert app[0]["timestamp"] == (stamp + timedelta(seconds=1)).timestamp()
        assert "private@example.com" not in json.dumps(snapshot.__dict__)
        assert training_snapshot(db) == reference
        base = load_snapshot(training_snapshot(db, False))
        assert len(base.events) == 30


def test_research_job_queues_pinned_data_and_worker_loads_it(client, tmp_path, monkeypatch):
    from atlasrec_api import main, worker
    from atlasrec_api.db import Job, SessionLocal
    headers = credentials(client)
    response = client.post("/api/v1/auth/login", headers=headers, json={"email": "admin@atlasrec.local", "password": "AtlasDemo!2026"})
    headers["x-csrf-token"] = response.json()["csrf_token"]
    install_fixture(monkeypatch, tmp_path)
    queued = []
    monkeypatch.setattr(main.celery, "send_task", lambda *args, **kwargs: queued.append(kwargs))
    response = client.post("/api/v1/admin/jobs", headers=headers, json={"model": "item_cf", "epochs": 2})
    assert response.status_code == 202, response.text
    job_id = response.json()["id"]
    assert queued[0]["args"] == [job_id]
    def training(config, data, progress):
        assert config["refit_for_serving"] is True
        assert data.manifest["synthetic"] is False
        assert len(data.events) == 30
        assert all(not event["user"].startswith("synthetic") for event in data.events)
        return {"manifest": data.manifest, "runs": []}
    monkeypatch.setattr(worker, "run", training)
    assert worker.train_job.run(job_id)["status"] == "completed"
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        assert job.config["dataset_id"] == "research-unit-fixture"
        assert job.status == "completed"


def test_research_promotion_rejects_wrong_dataset_and_missing_catalog_items(client, tmp_path, monkeypatch):
    from atlasrec_api import lifecycle
    from atlasrec_api.db import DatasetVersion, ModelVersion, Product, Run, SessionLocal, User
    from sqlalchemy import select
    manifest = install_fixture(monkeypatch, tmp_path)
    from types import SimpleNamespace
    bundle_manifest = {"profile": "research", "dataset_id": manifest["dataset_id"]}
    model = SimpleNamespace(f=SimpleNamespace(ids=["real-0", "real-1"]))
    monkeypatch.setattr(lifecycle, "load_bundle", lambda path: (model, bundle_manifest))
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.admin.is_(True)))
        db.add(Run(id="research-version", profile="research", dataset_id=manifest["dataset_id"], status="completed", record={"model": "item_cf"}))
        db.flush()
        db.add(ModelVersion(id="research-version", run_id="research-version", profile="research", path="fixture", validated=True))
        db.commit()
        db.get(Product, "real-1").available = False
        db.commit()
        with pytest.raises(ValueError, match="missing"):
            lifecycle.promote(db, "research-version", admin.id)
        db.get(Product, "real-1").available = True
        dataset = db.get(DatasetVersion, manifest["dataset_id"])
        dataset.manifest = {**dataset.manifest, "synthetic": True}
        db.commit()
        with pytest.raises(ValueError, match="not installed"):
            lifecycle.promote(db, "research-version", admin.id)
        dataset.manifest = {**dataset.manifest, "synthetic": False}
        db.commit()
        lifecycle.promote(db, "research-version", admin.id)
        assert db.get(ModelVersion, "research-version").active
