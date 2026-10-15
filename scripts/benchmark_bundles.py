"""Measure already-trained bundles without retraining experiments."""
import json
from pathlib import Path

from atlasrec_ml.bundle import load_bundle
from atlasrec_ml.pipeline import serving_benchmark

report=json.loads(Path("docs/evidence/demo-benchmark.json").read_text(encoding="utf-8"))
results=[]
for run in report["runs"]:
    if run["status"]=="completed":
        model,_=load_bundle(run["bundle"])
        results.append({"model":run["model"],"version":run["id"],**serving_benchmark(model)})
Path("docs/evidence/model-serving-benchmark.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
print(json.dumps(results,indent=2))
