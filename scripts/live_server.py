"""Live production-grade local server running the 20,500-product, 250-category real Amazon catalog."""
from __future__ import annotations

import os
from pathlib import Path

os.environ["ATLASREC_PROFILE"] = "research"
os.environ["ATLASREC_ENV"] = "test"
os.environ["RESEARCH_DATASET_ID"] = "58ef700cbbdd0206"
os.environ["ARTIFACT_DIR"] = str(Path("artifacts").resolve())
os.environ["DATA_DIR"] = str(Path("data").resolve())
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path("data/atlasrec-live.db").resolve()).replace("\\", "/")
os.environ["REDIS_URL"] = "redis://localhost:6379/15"

import uvicorn
from atlasrec_api import cache
from atlasrec_api.main import app
from atlasrec_api.queue import celery
from atlasrec_api.settings import settings

settings.profile = "research"
settings.research_dataset_id = "58ef700cbbdd0206"
settings.artifact_dir = Path("artifacts").resolve()
settings.data_dir = Path("data").resolve()


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

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
