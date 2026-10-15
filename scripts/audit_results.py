"""Produce compact, source-grounded comparisons without changing the evaluation."""
import json
import statistics
from collections import defaultdict
from pathlib import Path


def report(profile):
    path = Path("docs/evidence") / (profile + "-benchmark.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    grouped = defaultdict(list)
    for run in data["runs"]:
        grouped[run["model"]].append(run)
    output = {"profile": profile, "synthetic": profile == "demo",
              "dataset_id": data["manifest"]["dataset_id"], "split_id": data["manifest"]["split_id"],
              "rows": data["manifest"].get("row_count"), "models": {}}
    for name, runs in grouped.items():
        complete = [r for r in runs if r["status"] == "completed"]
        values = [r["metrics"]["ndcg@10"] for r in complete]
        output["models"][name] = {
            "runs": len(complete), "seeds": [r["seed"] for r in complete],
            "ndcg_at_10_mean": statistics.mean(values) if values else None,
            "ndcg_at_10_stdev": statistics.stdev(values) if len(values) > 1 else None,
            "test_queries": [r["metrics"]["queries"] for r in complete],
            "test_excluded": [r["metrics"]["excluded_no_eligible_positive"] for r in complete],
            "validation_ndcg": [r["validation"]["ndcg@10"] for r in complete],
            "training_seconds": [r["training_seconds"] for r in complete],
            "warm_queries": [sum(u["history_size"] >= 5 for u in r["metrics"]["user_rows"]) for r in complete],
        }
    destination = Path("docs/evidence") / (profile + "-summary.json")
    destination.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
for profile in ("demo", "research"):
    report(profile)
