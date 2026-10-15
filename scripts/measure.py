import json
import platform
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

BASE = "http://127.0.0.1:8000/api/v1/recommendations"


def request(_):
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(BASE, timeout=10) as response:
            data = json.load(response)
            assert data["items"]
        return (time.perf_counter() - start) * 1000, False
    except Exception:
        return (time.perf_counter() - start) * 1000, True


for i in range(20):
    request(i)
started = time.perf_counter()
with ThreadPoolExecutor(max_workers=10) as pool:
    samples = list(pool.map(request, range(200)))
elapsed = time.perf_counter() - started
values = [s[0] for s in samples]
report = {"workload": "HTTP API, isolated SQLite browser fixture; not Docker/PostgreSQL benchmark",
          "requests": 200, "warmup": 20, "concurrency": 10, "catalog": 200,
          "cache": "Redis unavailable, fallback observed", "errors": sum(s[1] for s in samples),
          "p50_ms": float(np.quantile(values, 0.5)), "p95_ms": float(np.quantile(values, 0.95)),
          "throughput_per_second": 200 / elapsed, "platform": platform.platform()}
Path("docs/evidence/http-benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
