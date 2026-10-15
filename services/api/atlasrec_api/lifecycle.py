from __future__ import annotations

import threading
import uuid

from atlasrec_ml.bundle import load_bundle
from sqlalchemy import select

from .db import Audit, DatasetVersion, ModelVersion, Product, Run, User
from .security import hasher
from .settings import settings

bundle_lock = threading.RLock()
# (version_id, model) replaced as one tuple so readers never see a mismatched pair.
_serving: tuple[str | None, object | None] = (None, None)


def reset_serving_cache():
    """Forget the in-process model. Used by tests and after destructive resets."""
    global _serving
    with bundle_lock:
        _serving = (None, None)


def active_bundle(db):
    """Return (model, version_id) for the active version, loading it once per process.

    The database is consulted on every call so a promotion made by any process is picked
    up on the next request. The lock is held only while a new bundle is read from disk,
    so concurrent requests on the common path never wait on each other.
    """
    global _serving
    row = db.execute(select(ModelVersion.id, ModelVersion.path).where(
        ModelVersion.profile == settings.profile, ModelVersion.active.is_(True))).first()
    if row is None:
        return None, None
    version_id, model = _serving
    if version_id == row.id:
        return model, version_id
    with bundle_lock:
        version_id, model = _serving
        if version_id != row.id:
            model, metadata = load_bundle(row.path)
            if metadata["profile"] != settings.profile:
                raise ValueError("Bundle operating profile mismatch")
            _serving = (row.id, model)
            version_id = row.id
        return model, version_id


def promote(db, version_id, actor, action="promote"):
    global _serving
    version = db.get(ModelVersion, version_id)
    if not version or version.profile != settings.profile or not version.validated:
        raise ValueError("A validated model in the current profile is required")
    run = db.get(Run, version.run_id)
    if not run or run.profile != settings.profile or run.status != "completed":
        raise ValueError("Incomplete runs cannot be activated")
    model, manifest = load_bundle(version.path)
    if manifest["profile"] != settings.profile:
        raise ValueError("Bundle profile mismatch")
    if settings.profile == "research":
        from .research import configured_dataset
        catalog_dataset = configured_dataset(db)
        trained_dataset = db.get(DatasetVersion, run.dataset_id)
        if (not trained_dataset or trained_dataset.profile != "research" or
                trained_dataset.manifest.get("synthetic") is not False or
                trained_dataset.manifest.get("base_dataset_id", trained_dataset.id) != catalog_dataset.id or
                manifest.get("dataset_id") != trained_dataset.id):
            raise ValueError("Model must be trained on the installed real catalog dataset")
        catalog_ids = set(db.scalars(select(Product.id).where(Product.profile == "research", Product.available.is_(True))).all())
        if not set(model.f.ids).issubset(catalog_ids):
            raise ValueError("Model product identifiers are missing from the installed catalog")
    with bundle_lock:
        db.refresh(version)
        active = db.scalars(select(ModelVersion).where(ModelVersion.profile == settings.profile,
                            ModelVersion.active.is_(True)).execution_options(populate_existing=True)).all()
        if version.active:
            return
        previous = [v.id for v in active]
        for v in active:
            v.active = False
        version.active = True
        db.add(Audit(id=str(uuid.uuid4()), actor_id=actor, action=action,
                     details={"profile": settings.profile, "previous": previous, "next": version.id}))
        db.commit()
        _serving = (version.id, model)


def register_report(db, report):
    manifest = report["manifest"]
    if manifest["profile"] != settings.profile or (settings.profile == "research" and manifest.get("synthetic") is not False):
        raise ValueError("Experiment report must match the active data profile")
    if not db.get(DatasetVersion, manifest["dataset_id"]):
        db.add(DatasetVersion(id=manifest["dataset_id"], profile=manifest["profile"], manifest=manifest))
        db.flush()
    for record in report["runs"]:
        if record["profile"] != manifest["profile"] or record["dataset_id"] != manifest["dataset_id"]:
            raise ValueError("Run provenance differs from its dataset manifest")
        if db.get(Run, record["id"]):
            continue
        db.add(Run(id=record["id"], dataset_id=record["dataset_id"], profile=record["profile"],
                   status=record["status"], record=record))
        db.flush()
        if record["status"] == "completed":
            load_bundle(record["bundle"])
            db.add(ModelVersion(id=record["id"], run_id=record["id"], profile=record["profile"],
                                path=record["bundle"], validated=True, active=False))
    db.commit()


def seed_catalog(db, data):
    if settings.profile != "demo":
        raise ValueError("Demo seed is disabled outside the demo profile")
    for product in data.products:
        if not db.get(Product, product["id"]):
            db.add(Product(**product, profile="demo"))
    if not db.scalar(select(User).where(User.email == settings.demo_admin_email)):
        db.add(User(id=str(uuid.uuid4()), email=settings.demo_admin_email, name="Demo administrator",
                    password_hash=hasher.hash(settings.demo_admin_password), admin=True, preferences=[]))
    db.commit()
