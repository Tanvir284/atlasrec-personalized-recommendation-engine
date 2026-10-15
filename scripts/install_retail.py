"""Install a trusted real catalog/report and activate a validation-selected model."""
import argparse
import json
from pathlib import Path

from atlasrec_api.db import SessionLocal, User
from atlasrec_api.lifecycle import promote, register_report
from atlasrec_api.research import install_research_catalog
from atlasrec_api.settings import settings
from atlasrec_ml.data import Dataset
from sqlalchemy import select


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--model", choices=["auto", "item_cf", "two_tower", "popularity"], default="auto")
    args = parser.parse_args()
    data = Dataset.load(Path(args.dataset))
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    if settings.profile != "research" or report["manifest"]["dataset_id"] != data.manifest["dataset_id"]:
        raise ValueError("Research profile and matching dataset/report required")
    if settings.research_dataset_id != data.manifest["dataset_id"]:
        raise ValueError("RESEARCH_DATASET_ID must match the catalog")
    completed = [r for r in report["runs"] if r["status"] == "completed"]
    candidates = [r for r in completed if r.get("serving_refit", {}).get("status") == "completed"
                  and r.get("validation", {}).get("queries", 0) >= 20]
    if args.model != "auto":
        candidates = [r for r in candidates if r["model"] == args.model]
    else:
        # Personalized retrieval is the deployment objective; retain popularity as a measured baseline.
        candidates = [r for r in candidates if r["model"] != "popularity"] or candidates
    if not candidates:
        raise ValueError("No completed serving model with sufficient validation evidence")
    selected = max(candidates, key=lambda r: r["validation"].get("warm_ndcg@10") or r["validation"]["ndcg@10"])
    for record in completed:
        record["original_bundle_location"] = record["bundle"]
        record["bundle"] = str(settings.artifact_dir.resolve() / record["id"])
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.admin.is_(True)))
        if admin is None:
            raise ValueError("Create an administrator before installing the real catalog")
        manifest = install_research_catalog(db, data)
        register_report(db, report)
        promote(db, selected["id"], admin.id)
    print(json.dumps({"dataset_id": manifest["dataset_id"], "products": manifest["product_count"],
                      "historical_reviews": manifest["row_count"], "historical_reviewers": manifest["user_count"],
                      "active_model": selected["id"], "model": selected["model"],
                      "selection": "Best validation warm NDCG among completed personalized models; test metrics not used",
                      "validation_ndcg10": selected["validation"]["ndcg@10"],
                      "test_ndcg10": selected["metrics"]["ndcg@10"]}, indent=2))


if __name__ == "__main__":
    main()
