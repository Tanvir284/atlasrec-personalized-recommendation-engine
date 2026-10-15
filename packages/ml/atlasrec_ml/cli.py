import argparse
import json
from pathlib import Path

import yaml

from .bundle import load_bundle
from .data import demo, research, temporal_split
from .pipeline import run, serving_benchmark


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["generate", "ingest", "validate", "split", "train", "evaluate", "benchmark"])
    p.add_argument("--config", default="configs/benchmark.yaml")
    p.add_argument("--bundle")
    args = p.parse_args()
    config = yaml.safe_load(Path(args.config).read_text())
    if args.command in ("evaluate", "benchmark") and args.bundle:
        model, _ = load_bundle(args.bundle)
        if args.command == "benchmark":
            result = serving_benchmark(model)
        else:
            from .evaluate import evaluate
            dataset = (research(config) if config.get("profile") == "research" else
                       demo(config.get("seed", 42), config.get("products", 200),
                            config.get("users", 100), config.get("interactions", 3000)))
            result = evaluate(model, temporal_split(dataset, config.get("positive_threshold", 4))["test"])
        print(json.dumps(result, indent=2))
        return
    if args.command in ("generate", "ingest", "validate", "split"):
        dataset = (research(config) if config.get("profile") == "research" else
                   demo(config.get("seed", 42), config.get("products", 200),
                        config.get("users", 100), config.get("interactions", 3000)))
        dataset.save(Path("data") / (dataset.manifest["dataset_id"] + ".json"))
        print(json.dumps(dataset.manifest, indent=2))
        if args.command == "split":
            print(temporal_split(dataset, config.get("positive_threshold", 4))["boundaries"])
        return
    report = run(config)
    for r in report["runs"]:
        print(r["id"], r["status"], r.get("metrics", {}).get("ndcg@10", r.get("error")))
    if args.command == "benchmark":
        benchmarks = []
        for record in report["runs"]:
            if record["status"] == "completed":
                model, _ = load_bundle(record["bundle"])
                benchmarks.append({"model": record["model"], "version": record["id"], **serving_benchmark(model)})
        destination = Path("docs/evidence/model-serving-benchmark.json")
        destination.write_text(json.dumps(benchmarks, indent=2), encoding="utf-8")
    if any(r["status"] != "completed" for r in report["runs"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
