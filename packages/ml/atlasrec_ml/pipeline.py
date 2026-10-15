from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import time
import uuid
from pathlib import Path

import mlflow
import numpy as np

from .bundle import load_bundle, save_bundle
from .data import Dataset, demo, research, temporal_split
from .evaluate import evaluate, paired_difference
from .models import Recommender
from .resources import observed_memory


def source_hash():
    h = hashlib.sha256()
    for root in (Path("packages/ml"), Path("services/api")):
        for p in sorted(root.rglob("*.py")):
            h.update(p.read_bytes())
    return h.hexdigest()


def run(config, data=None, progress=None):
    evidence_name = config.get("evidence_name", config.get("profile", "demo"))
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", evidence_name):
        raise ValueError("Invalid evidence_name; use a short lowercase filename label")
    data = data or (demo(config.get("seed", 42), config.get("products", 200),
                         config.get("users", 100), config.get("interactions", 3000))
                    if config.get("profile", "demo") == "demo" else research(config))
    evaluation_data = data
    if data.manifest["profile"] == "research" and config.get("refit_for_serving"):
        evaluation_data = Dataset(data.products, [e for e in data.events if e["kind"] == "imported_review"], data.manifest)
    split = temporal_split(evaluation_data, config.get("positive_threshold", 4))
    data.manifest.update({"boundaries": split["boundaries"], "split_id": split["split_id"]})
    data_dir = Path(os.getenv("DATA_DIR", "data"))
    artifact_dir = Path(os.getenv("ARTIFACT_DIR", "artifacts"))
    data.save(data_dir / (data.manifest["dataset_id"] + ".json"))
    artifact_dir.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "sqlite:///" + str((artifact_dir / "mlflow.db").resolve()).replace("\\", "/")))
    # Explicit persistent artifact URI; the application image root is read-only.
    # v1 preserves earlier experiments with legacy/default artifact locations.
    experiment_name = "atlasrec-" + data.manifest["profile"] + "-bundles-v1"
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        experiment_id = mlflow.create_experiment(experiment_name, artifact_location=(artifact_dir / "mlruns").resolve().as_uri())
    else:
        experiment_id = experiment.experiment_id
    mlflow.set_experiment(experiment_id=experiment_id)
    results = []
    names = config.get("models", ["popularity"])
    for seed in config.get("seeds", [config.get("seed", 42)]):
        for name in names:
            version = name + "-" + uuid.uuid4().hex[:12]
            record = {
                "id": version, "model": name, "seed": seed, "profile": data.manifest["profile"],
                "synthetic": data.manifest["synthetic"], "dataset_id": data.manifest["dataset_id"],
                "split_id": split["split_id"], "config": {**config, "seed": seed},
                "evaluation_scope": "Historical source reviews only; application feedback enters serving refit" if evaluation_data is not data else "Chronological dataset holdout",
                "source_hash": source_hash(), "hardware": {"platform": platform.platform(), "threads": os.cpu_count()},
            }
            start = time.monotonic()
            with mlflow.start_run(run_name=version) as tracked:
                record["mlflow_run_id"] = tracked.info.run_id
                record["mlflow_experiment_id"] = experiment_id
                mlflow.log_params({"model": name, "seed": seed, "dataset_id": record["dataset_id"], "split_id": record["split_id"]})
                try:
                    with observed_memory() as memory:
                        model = Recommender(name, record["config"]).fit(data.products, split["train"], split["validation"], progress)
                    record.update(memory)
                    validation = evaluate(model, split["validation"])
                    test = evaluate(model, split["test"])
                    reranked = evaluate(model, split["test"], diversity=0.1)
                    record.update({
                        "status": model.fit_status, "best_epoch": model.best_epoch,
                        "validation": validation, "metrics": test, "diversity_metrics": reranked,
                        "training_seconds": model.training_seconds, "rank_groups": getattr(model, "rank_groups", None),
                        "excluded_rank_groups": model.excluded_rank_groups,
                    })
                    serving_model = model
                    if config.get("refit_for_serving", False):
                        # Offline metrics above use only the chronological training partition.
                        # Deployment can then learn all known feedback, including new app users.
                        serving_config = {**record["config"], "epochs": model.best_epoch or config.get("epochs", 12)}
                        with observed_memory() as serving_memory:
                            serving_model = Recommender(name, serving_config).fit(data.products, data.events, progress=progress)
                        record["serving_refit"] = {
                            "evaluation_before_refit": True,
                            "event_count": len(data.events),
                            "latest_event_timestamp": max(e["timestamp"] for e in data.events),
                            "app_feedback_events": sum(e["kind"] != "imported_review" for e in data.events),
                            "status": serving_model.fit_status,
                            "training_seconds": serving_model.training_seconds,
                            **serving_memory,
                        }
                        if serving_model.fit_status != "completed":
                            raise ValueError("Serving refit did not complete within its resource budget")
                    bundle_path = artifact_dir / version
                    manifest = save_bundle(serving_model, bundle_path, {
                        "version": version, "dataset_id": record["dataset_id"], "split_id": record["split_id"],
                        "source_hash": record["source_hash"], "profile": record["profile"],
                        "serving_refit": record.get("serving_refit"),
                    })
                    loaded, _ = load_bundle(bundle_path)
                    user = serving_model.f.users[0]
                    hist = [serving_model.f.ids[i] for i in serving_model.f.histories[user]]
                    if loaded.recommend(user, hist) != serving_model.recommend(user, hist):
                        raise ValueError("Save/load inference parity failed")
                    record["bundle"] = str(bundle_path.resolve())
                    record["bundle_manifest"] = manifest
                    record["artifact_bytes"] = sum(p.stat().st_size for p in bundle_path.iterdir())
                    mlflow.log_metrics({k.replace(chr(64), chr(95)+chr(97)+chr(116)+chr(95)): v for k, v in test.items() if isinstance(v, (float, int))})
                    mlflow.log_artifacts(str(bundle_path), "bundle")
                except Exception as exc:
                    record.update({"status": "failed", "error": str(exc)})
                    mlflow.set_tag("failure", str(exc))
                record["total_seconds"] = time.monotonic() - start
                results.append(record)
                (artifact_dir / (version + ".json")).write_text(json.dumps(record, indent=2), encoding="utf-8")
    successful = [r for r in results if r["status"] == "completed"]
    report = {"manifest": data.manifest, "split": {k: v for k, v in split.items() if k not in ("train", "validation", "test")},
              "runs": results, "comparisons": [], "cold_item": None}
    if len(successful) > 1:
        baseline = successful[0]
        for r in successful[1:]:
            report["comparisons"].append({"a": baseline["id"], "b": r["id"],
                                         **paired_difference(baseline["metrics"], r["metrics"])})
    if config.get("cold_item_fraction", 0) and successful:
        base = successful[0]
        rng = np.random.default_rng(config.get("seed", 42))
        eligible = sorted({e["item"] for e in split["train"]})
        withheld = rng.choice(eligible, max(1, int(len(eligible) * config["cold_item_fraction"])), replace=False).tolist()
        # Preserve availability evidence in the feature ID map, but withhold positive signals.
        cold_train = [{**e, "rating": 1} if e["item"] in withheld else e for e in split["train"]]
        cold = Recommender("two_tower", {**config, "content_only_ids": withheld, "epochs": min(6, config.get("epochs", 12))}).fit(data.products, cold_train)
        report["cold_item"] = {"method": "eligible-item collaborative interaction withholding",
                               "id_embedding": "masked to zero; retained item vectors use only permitted content", "withheld_count": len(withheld), "withheld_ids": withheld,
                               "metrics": evaluate(cold, split["test"], positives_only=withheld), "reference_run": base["id"]}
    evidence = Path("docs/evidence")
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / (evidence_name + "-benchmark.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def serving_benchmark(model, count=200, concurrency=10):
    from concurrent.futures import ThreadPoolExecutor
    user = model.f.users[0]
    hist = [model.f.ids[i] for i in model.f.histories[user]]
    for _ in range(20):
        model.recommend(user, hist)
    def one(_):
        started = time.perf_counter()
        model.recommend(user, hist)
        return (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        values = list(pool.map(one, range(count)))
    duration = time.perf_counter() - started
    return {"workload": "in-process model inference; excludes API/DB/Redis/network",
            "requests": count, "concurrency": concurrency, "warmup": 20,
            "catalog": len(model.f.ids), "cache": "none", "errors": 0,
            "p50_ms": float(np.quantile(values, 0.5)), "p95_ms": float(np.quantile(values, 0.95)),
            "throughput_per_second": count / duration,
            "hardware": {"platform": platform.platform(), "threads": os.cpu_count()}}
