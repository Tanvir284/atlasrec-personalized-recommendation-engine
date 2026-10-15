"""Trusted research catalog installation and immutable application-feedback snapshots."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import timezone
from pathlib import Path

from atlasrec_ml.data import Dataset, digest
from sqlalchemy import func, select

from .db import DatasetVersion, Event, ModelVersion, Product, User
from .settings import settings

PRODUCT_FIELDS = ("id", "title", "description", "category", "price", "currency", "image", "available")


def _validate(data):
    manifest = data.manifest
    if settings.profile != "research" or manifest.get("profile") != "research" or manifest.get("synthetic") is not False:
        raise ValueError("Only a real research dataset can be installed in the research profile")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", str(manifest.get("dataset_id", ""))):
        raise ValueError("Invalid research dataset identifier")
    ids = [p["id"] for p in data.products]
    if not ids or len(ids) != len(set(ids)) or any(item.startswith("demo-") for item in ids):
        raise ValueError("Research catalog must have unique non-demo products")
    catalog_ids = set(ids)
    if not data.events or any(e["item"] not in catalog_ids for e in data.events):
        raise ValueError("Research events must refer to this catalog")


def _save_immutable(data, directory):
    path = settings.data_dir.resolve() / directory / (data.manifest["dataset_id"] + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(data.__dict__, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError("An immutable dataset with this ID already has different contents")
    else:
        # Exclusive creation prevents two publishers from overwriting one immutable snapshot.
        with path.open("xb") as handle:
            handle.write(encoded)
    return {"dataset_path": str(path), "dataset_sha256": digest(path)}


def load_snapshot(reference):
    root = settings.data_dir.resolve()
    path = Path(reference["dataset_path"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Dataset snapshot must be inside the configured data directory")
    if digest(path) != reference["dataset_sha256"]:
        raise ValueError("Dataset snapshot checksum mismatch")
    data = Dataset.load(path)
    _validate(data)
    if data.manifest["dataset_id"] != reference["dataset_id"]:
        raise ValueError("Dataset snapshot identity mismatch")
    return data


def install_research_catalog(db, data):
    """Install source products only; historical reviewers never become app accounts."""
    _validate(data)
    ids = {p["id"] for p in data.products}
    existing = {p.id: p for p in db.scalars(select(Product)).all()}
    if any(item in existing and existing[item].profile != "research" for item in ids):
        raise ValueError("Product identifiers collide with a different operating profile")
    active = db.scalar(select(ModelVersion).where(ModelVersion.profile == "research", ModelVersion.active.is_(True)))
    if active:
        from atlasrec_ml.bundle import load_bundle
        model, _ = load_bundle(active.path)
        if not set(model.f.ids).issubset(ids):
            raise ValueError("New catalog is incompatible with the active model; retain its product IDs")
    reference = _save_immutable(data, "catalog")
    manifest = {**data.manifest, **reference,
                "product_count": len(data.products), "row_count": len(data.events),
                "user_count": len({e["user"] for e in data.events})}
    registered = db.get(DatasetVersion, manifest["dataset_id"])
    if registered and registered.profile != "research":
        raise ValueError("Dataset identifier belongs to a different profile")
    if registered:
        previous = registered.manifest.get("dataset_sha256")
        if previous and previous != reference["dataset_sha256"]:
            raise ValueError("Registered dataset checksum differs")
        registered.manifest = {**registered.manifest, **manifest}
    else:
        db.add(DatasetVersion(id=manifest["dataset_id"], profile="research", manifest=manifest))
    for product in existing.values():
        if product.profile == "research" and product.id not in ids:
            product.available = False
    for item in data.products:
        product = existing.get(item["id"])
        fields = {name: item[name] for name in PRODUCT_FIELDS}
        if product is None:
            db.add(Product(**fields, profile="research"))
        else:
            for name, value in fields.items():
                setattr(product, name, value)
    db.commit()
    return manifest


def configured_dataset(db):
    if not settings.research_dataset_id:
        raise ValueError("Set RESEARCH_DATASET_ID to an installed real dataset before training")
    record = db.get(DatasetVersion, settings.research_dataset_id)
    if not record or record.profile != "research" or record.manifest.get("synthetic") is not False:
        raise ValueError("Configured research dataset is not installed")
    return record


def training_snapshot(db, include_application_feedback=True):
    record = configured_dataset(db)
    data = load_snapshot({**record.manifest, "dataset_id": record.id})
    if not include_application_feedback:
        return {"dataset_id": record.id, "dataset_path": record.manifest["dataset_path"],
                "dataset_sha256": record.manifest["dataset_sha256"]}
    ids = {p["id"] for p in data.products}
    # Explicit preferences only. Views and impressions are not invented review ratings.
    rows = db.scalars(select(Event).join(User, User.id == Event.user_id).where(
        Event.profile == "research", User.admin.is_(False),
        Event.kind.in_(["rating", "favorite", "dismiss"])).order_by(Event.created_at, Event.id)).all()
    latest = {}
    for event in rows:
        if event.item_id in ids:
            latest[(event.user_id, event.item_id)] = event
    if not latest:
        return {"dataset_id": record.id, "dataset_path": record.manifest["dataset_path"],
                "dataset_sha256": record.manifest["dataset_sha256"]}
    feedback = []
    for event in latest.values():
        timestamp = event.created_at
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        feedback.append({"id": "app:" + event.id, "user": "app:" + event.user_id,
                         "item": event.item_id, "timestamp": timestamp.timestamp(),
                         "rating": event.rating if event.kind == "rating" else 5 if event.kind == "favorite" else 1,
                         "kind": "application_" + event.kind})
    identity = hashlib.sha256(json.dumps([record.id, feedback], sort_keys=True).encode()).hexdigest()[:24]
    manifest = {**data.manifest, "dataset_id": "feedback-" + identity, "base_dataset_id": record.id,
                "application_feedback_count": len(feedback),
                "application_user_count": len({e["user"] for e in feedback}),
                "application_feedback_policy": "latest explicit rating/favorite/dismiss per signed-in non-admin account and product; server time; separate app namespace",
                "row_count": len(data.events) + len(feedback)}
    snapshot = Dataset(data.products, sorted(data.events + feedback, key=lambda e: (e["timestamp"], e["id"])), manifest)
    return {"dataset_id": manifest["dataset_id"], **_save_immutable(snapshot, "snapshots")}


def catalog_information(db):
    from .lifecycle import active_bundle
    record = db.get(DatasetVersion, settings.research_dataset_id) if settings.research_dataset_id else None
    manifest = record.manifest if record and record.profile == settings.profile else {}
    version = db.scalar(select(ModelVersion).where(ModelVersion.profile == settings.profile, ModelVersion.active.is_(True)))
    products = db.scalar(select(func.count()).select_from(Product).where(Product.profile == settings.profile, Product.available.is_(True)))
    events = db.scalar(select(func.count()).select_from(Event).where(Event.profile == settings.profile, Event.user_id.is_not(None)))
    from .db import Run
    run = db.get(Run, version.run_id) if version else None
    try:
        ready = active_bundle(db)[0] is not None
    except Exception:
        ready = False
    return {"profile": settings.profile, "synthetic": settings.profile == "demo",
            "dataset_id": record.id if manifest else None, "source": manifest.get("source"),
            "terms_url": manifest.get("terms"), "product_count": products,
            "historical_interactions": manifest.get("row_count", 0),
            "historical_reviewers": manifest.get("user_count", 0),
            "recorded_application_events": events,
            "price_note": "Historical source catalog price; current merchant price and stock are not verified",
            "personalization": {"active_model_version": version.id if version else None,
                                "model_type": run.record.get("model") if run else None,
                                "trained_at": version.created_at.isoformat() if version else None,
                                "status": "ready" if ready else "fallback"}}
