from __future__ import annotations

import importlib.metadata
import json
import platform
from pathlib import Path

import faiss
import joblib
import numpy as np

from .data import digest

DEPENDENCIES = ["numpy", "scikit-learn", "torch", "lightgbm", "faiss-cpu"]
SCHEMA = 1


def versions():
    return {p: importlib.metadata.version(p) for p in DEPENDENCIES}


def save_bundle(model, path, metadata):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    joblib.dump(model, path / "model.joblib", compress=3)
    (path / "index.faiss").write_bytes(faiss.serialize_index(model.index).tobytes())
    (path / "ids.json").write_text(json.dumps(model.f.ids), encoding="utf-8")
    manifest = {
        **metadata, "schema": SCHEMA, "name": model.name, "dimension": model.item_vectors.shape[1],
        "items": len(model.f.ids), "dependencies": versions(),
        "python": ".".join(platform.python_version_tuple()[:2]), "config": model.config,
        "files": {p.name: digest(p) for p in path.iterdir() if p.is_file()},
    }
    (path / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_bundle(path):
    path = Path(path)
    m = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if m["schema"] != SCHEMA or m["dependencies"] != versions():
        raise ValueError("Incompatible bundle schema or dependency versions")
    if m["python"] != ".".join(platform.python_version_tuple()[:2]):
        raise ValueError("Incompatible Python version")
    expected = {"model.joblib", "index.faiss", "ids.json"}
    if set(m["files"]) != expected:
        raise ValueError("Invalid bundle file inventory")
    for name, checksum in m["files"].items():
        if digest(path / name) != checksum:
            raise ValueError("Corrupt artifact: " + name)
    # Only load trusted, locally trained artifacts; arbitrary uploaded pickle is unsupported.
    model = joblib.load(path / "model.joblib")
    index = faiss.deserialize_index(np.frombuffer((path / "index.faiss").read_bytes(), dtype=np.uint8).copy())
    ids = json.loads((path / "ids.json").read_text(encoding="utf-8"))
    if ids != model.f.ids or len(set(ids)) != len(ids):
        raise ValueError("Bundle ID map mismatch")
    if index.ntotal != len(ids) or index.d != m["dimension"] or model.item_vectors.shape != (len(ids), index.d):
        raise ValueError("Index/embedding dimensions mismatch")
    if not np.allclose(index.reconstruct_n(0, index.ntotal), model.item_vectors, atol=1e-6):
        raise ValueError("Index does not match model embeddings")
    model.index = index
    return model, m
