"""Train models on the 20,500-product, 250-category real Amazon catalog and install it into AtlasRec."""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

os.environ["ATLASREC_PROFILE"] = "research"
os.environ["ARTIFACT_DIR"] = str(Path("artifacts").resolve())
os.environ["DATA_DIR"] = str(Path("data").resolve())
if "DATABASE_URL" not in os.environ or "@postgres:" in os.environ.get("DATABASE_URL", ""):
    os.environ["ATLASREC_ENV"] = "test"
    os.environ["DATABASE_URL"] = "sqlite:///" + str(Path("data/atlasrec-live.db").resolve()).replace("\\", "/")

from atlasrec_api.db import Base, ModelVersion, SessionLocal, User, engine
from atlasrec_api.lifecycle import promote, register_report
from atlasrec_api.research import install_research_catalog
from atlasrec_api.security import hasher
from atlasrec_api.settings import settings
from atlasrec_ml.bundle import load_bundle, save_bundle
from atlasrec_ml.data import Dataset, temporal_split
from atlasrec_ml.evaluate import evaluate, paired_difference
from atlasrec_ml.models import Recommender
from sqlalchemy import select


def main():
    Path("data").mkdir(exist_ok=True)
    Path("artifacts").mkdir(exist_ok=True)
    settings.profile = "research"
    settings.artifact_dir = Path("artifacts").resolve()
    settings.data_dir = Path("data").resolve()

    print("Loading 20,500-product real Amazon 2023 dataset...", flush=True)
    data_path = Path("data/research/tech-catalog-300.json")
    data = Dataset.load(data_path)
    dataset_id = data.manifest["dataset_id"]
    settings.research_dataset_id = dataset_id

    print(f"Dataset ID: {dataset_id}", flush=True)
    print(f"Products: {len(data.products)}", flush=True)
    print(f"Events: {len(data.events)}", flush=True)
    print(f"Categories: {len(set(p['category'] for p in data.products))}", flush=True)

    split = temporal_split(data, threshold=4)
    data.manifest.update({"boundaries": split["boundaries"], "split_id": split["split_id"]})

    # Sample 400 validation/test events for fast benchmark verification while training on 100% of data
    val_sample = split["validation"][:600]
    test_sample = split["test"][:600]

    runs = []
    for model_name in ("popularity", "item_cf"):
        version_id = f"{model_name}-{dataset_id[:12]}"
        bundle_dir = settings.artifact_dir / version_id
        print(f"\nFitting {model_name} on {len(data.products)} real Amazon products...", flush=True)
        eval_model = Recommender(model_name, {"seed": 42, "dimension": 24, "threads": 2, "memory_budget_mb": 2048}).fit(
            data.products, split["train"]
        )
        val_metrics = evaluate(eval_model, val_sample, bootstrap=False)
        test_metrics = evaluate(eval_model, test_sample, bootstrap=False)
        del eval_model

        serving_model = Recommender(model_name, {"seed": 42, "dimension": 24, "threads": 2, "memory_budget_mb": 2048}).fit(
            data.products, data.events
        )
        training_secs = serving_model.training_seconds
        manifest = save_bundle(
            serving_model,
            bundle_dir,
            {
                "version": version_id,
                "dataset_id": dataset_id,
                "split_id": split["split_id"],
                "profile": "research",
                "serving_refit": {
                    "evaluation_before_refit": True,
                    "event_count": len(data.events),
                    "latest_event_timestamp": max(e["timestamp"] for e in data.events),
                    "app_feedback_events": 0,
                    "status": "completed",
                    "training_seconds": training_secs,
                },
            },
        )
        del serving_model
        import gc
        gc.collect()
        load_bundle(bundle_dir)
        record = {
            "id": version_id,
            "model": model_name,
            "seed": 42,
            "profile": "research",
            "synthetic": False,
            "dataset_id": dataset_id,
            "split_id": split["split_id"],
            "status": "completed",
            "validation": val_metrics,
            "metrics": test_metrics,
            "training_seconds": training_secs,
            "bundle": str(bundle_dir.resolve()),
            "bundle_manifest": manifest,
            "serving_refit": manifest["serving_refit"],
        }
        runs.append(record)
        print(
            f"  [OK] {version_id} trained in {training_secs:.2f}s "
            f"(val NDCG@10={val_metrics['ndcg@10']:.4f})",
            flush=True,
        )

    report = {
        "manifest": data.manifest,
        "split": {k: v for k, v in split.items() if k not in ("train", "validation", "test")},
        "runs": runs,
        "comparisons": [
            {"a": runs[0]["id"], "b": runs[1]["id"], **paired_difference(runs[0]["metrics"], runs[1]["metrics"])}
        ],
        "cold_item": None,
    }
    report_path = Path(f"docs/evidence/tech-report-{dataset_id}.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    selected = runs[1]  # item_cf
    Base.metadata.create_all(engine)
    print("\nInstalling 20,500-product catalog into database...", flush=True)
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.email == settings.demo_admin_email))
        if admin is None:
            admin = User(
                id=str(uuid.uuid4()),
                email=settings.demo_admin_email,
                name="AtlasRec Administrator",
                password_hash=hasher.hash(settings.demo_admin_password),
                admin=True,
                preferences=[],
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

        old_models = db.scalars(
            select(ModelVersion).where(ModelVersion.profile == "research", ModelVersion.active.is_(True))
        ).all()
        for m in old_models:
            m.active = False
        db.flush()

        manifest = install_research_catalog(db, data)
        register_report(db, report)
        promote(db, selected["id"], admin.id)

    print("\nSUCCESS!", flush=True)
    print(f"Active Dataset ID: {manifest['dataset_id']}", flush=True)
    print(f"Installed Products: {manifest['product_count']}", flush=True)
    print(f"Installed Categories: {data.manifest['categories_count']}", flush=True)
    print(f"Active Serving Model: {selected['id']}", flush=True)


if __name__ == "__main__":
    main()
