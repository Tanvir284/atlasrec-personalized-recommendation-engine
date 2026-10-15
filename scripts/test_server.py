"""Isolated browser integration fixture; never used for the demo installation."""
import os
from pathlib import Path

os.environ["ATLASREC_PROFILE"] = "demo"
os.environ["ATLASREC_ENV"] = "test"
os.environ["ARTIFACT_DIR"] = str(Path("artifacts").resolve())
os.environ["DATA_DIR"] = str(Path("data").resolve())
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path("data/browser-test.db").resolve()).replace("\\", "/")
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
Path("data").mkdir(exist_ok=True)

from atlasrec_api.db import Base, DatasetVersion, ModelVersion, Run, SessionLocal, User, engine
from atlasrec_api.lifecycle import promote, seed_catalog
from atlasrec_api.settings import settings
from atlasrec_ml.bundle import load_bundle, save_bundle
from atlasrec_ml.data import demo, temporal_split
from atlasrec_ml.evaluate import evaluate
from atlasrec_ml.models import Recommender
from sqlalchemy import select

Base.metadata.create_all(engine)
data = demo()
with SessionLocal() as db:
    seed_catalog(db, data)
    if not db.scalar(select(ModelVersion).where(ModelVersion.active.is_(True))):
        path = Path("artifacts/browser-fixture")
        if not path.exists():
            model = Recommender("popularity").fit(data.products, data.events[:2100])
            save_bundle(model, path, {"version": "browser-popularity", "profile": "demo", "dataset_id": "browser-fixture", "split_id": "fixture"})
        load_bundle(path)
        if not db.get(DatasetVersion, "browser-fixture"):
            db.add(DatasetVersion(id="browser-fixture", profile="demo", manifest=data.manifest))
            db.flush()
            db.add(Run(id="browser-popularity", dataset_id="browser-fixture", profile="demo",
                       status="completed", record={"model": "popularity", "profile": "demo",
                       "seed": 42, "split_id": "fixture", "id": "browser-popularity",
                       "dataset_id": "browser-fixture", "status": "completed"}))
            db.flush()
            db.add(ModelVersion(id="browser-popularity", run_id="browser-popularity", profile="demo",
                                validated=True, active=False, path=str(path.resolve())))
            db.commit()
        admin = db.scalar(select(User).where(User.email == settings.demo_admin_email))
        promote(db, "browser-popularity", admin.id)

with SessionLocal() as db:
    version = db.get(ModelVersion, "browser-popularity")
    model, _ = load_bundle(version.path)
    run = db.get(Run, "browser-popularity")
    run.record = {**run.record, "synthetic": True, "metrics": evaluate(model, temporal_split(data)["test"]),
                  "validation": evaluate(model, temporal_split(data)["validation"]),
                  "training_seconds": model.training_seconds}
    db.commit()

import uvicorn
from atlasrec_api import cache
from atlasrec_api.main import app
from atlasrec_api.queue import celery


class _InMemoryPipeline:
    def __init__(self, store):
        self._store = store
        self._ops = []

    def zremrangebyscore(self, key, low, high):
        self._ops.append(("zremrangebyscore", key, low, high))

    def zcard(self, key):
        self._ops.append(("zcard", key))

    def zadd(self, key, mapping):
        self._ops.append(("zadd", key, mapping))

    def expire(self, key, ttl):
        self._ops.append(("expire", key, ttl))

    def execute(self):
        out = []
        for op in self._ops:
            kind = op[0]
            if kind == "zremrangebyscore":
                _, key, low, high = op
                bucket = self._store.zsets.setdefault(key, {})
                for member in [m for m, score in bucket.items() if low <= score <= high]:
                    bucket.pop(member, None)
                out.append(0)
            elif kind == "zcard":
                _, key = op
                out.append(len(self._store.zsets.get(key, {})))
            elif kind == "zadd":
                _, key, mapping = op
                self._store.zsets.setdefault(key, {}).update(mapping)
                out.append(len(mapping))
            elif kind == "expire":
                out.append(True)
        return out


class _InMemoryRedis:
    def __init__(self):
        self.kv = {}
        self.zsets = {}

    def get(self, key):
        return self.kv.get(key)

    def set(self, key, value, ex=None):
        self.kv[key] = value
        return True

    def delete(self, *keys):
        for k in keys:
            self.kv.pop(k, None)
            self.zsets.pop(k, None)
        return len(keys)

    def scan_iter(self, match="*"):
        prefix = match.rstrip("*")
        return [k for k in list(self.kv) if k.startswith(prefix)]

    def zrem(self, key, member):
        self.zsets.get(key, {}).pop(member, None)
        return 1

    def pipeline(self):
        return _InMemoryPipeline(self)


try:
    cache.client.ping()
except Exception:
    cache.client = _InMemoryRedis()
    if os.environ.get("EXPECT_QUEUE") != "1":
        celery.send_task = lambda *args, **kwargs: None

uvicorn.run(app, host="127.0.0.1", port=8000)

