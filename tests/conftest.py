import os
import tempfile
from pathlib import Path

import pytest

os.environ["ATLASREC_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get("ATLASREC_TEST_DATABASE_URL", "sqlite:///" + str(Path(tempfile.gettempdir()) / ("atlasrec-test-" + str(os.getpid()) + ".db")).replace("\\", "/"))
os.environ["MLFLOW_DISABLE_AGENT_HINT"] = "1"
# Environment variables win over the local `.env`, so pin the profile here to
# keep the suite hermetic when a developer runs the app in research/retail mode.
os.environ["ATLASREC_PROFILE"] = "demo"
os.environ["RESEARCH_DATASET_ID"] = ""


@pytest.fixture
def client(tmp_path):
    from atlasrec_api import lifecycle, ratelimit
    from atlasrec_api.db import Base, SessionLocal, User, engine
    from atlasrec_api.lifecycle import promote, register_report, seed_catalog
    from atlasrec_api.main import app
    from atlasrec_ml.bundle import save_bundle
    from atlasrec_ml.data import demo
    from atlasrec_ml.models import Recommender
    from fastapi.testclient import TestClient
    from sqlalchemy import select

    assert os.environ["ATLASREC_ENV"] == "test"
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    ratelimit.reset()
    lifecycle.reset_serving_cache()
    data = demo(products=40, users=10, interactions=400)
    model = Recommender("popularity").fit(data.products, data.events[:280])
    path = tmp_path / "bundle"
    save_bundle(model, path, {"version": "test-pop", "profile": "demo", "dataset_id": "test-data", "split_id": "test-split"})
    with SessionLocal() as db:
        seed_catalog(db, data)
        register_report(db, {"manifest": {**data.manifest, "dataset_id": "test-data"}, "runs": [{
            "id": "test-pop", "dataset_id": "test-data", "profile": "demo",
            "status": "completed", "bundle": str(path), "model": "popularity",
            "split_id": "test-split", "seed": 42, "metrics": {"recall@10": 0.0, "ndcg@10": 0.0},
        }]})
        admin = db.scalar(select(User).where(User.admin.is_(True)))
        promote(db, "test-pop", admin.id)
    with TestClient(app) as c:
        yield c


def credentials(client):
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    return {"origin": "http://localhost:3000", "x-csrf-token": token}
