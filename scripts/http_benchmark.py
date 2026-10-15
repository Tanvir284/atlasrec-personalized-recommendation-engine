"""Measure the actual same-origin Compose HTTP path; never relabel a fixture benchmark."""
import argparse
import http.cookiejar
import json
import os
import platform
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument("--base-url",default="http://127.0.0.1:3000")
parser.add_argument("--requests",type=int,default=200)
parser.add_argument("--clients",type=int,default=10)
args=parser.parse_args()
jar=http.cookiejar.CookieJar()
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
with opener.open(args.base_url+"/api/v1/products?limit=1",timeout=30) as response:
    catalog_size=json.load(response)["total"]
hardware={"host":platform.platform(),"logical_cpu_threads":os.cpu_count()}
if os.name=="nt":
    import ctypes
    class MemoryStatus(ctypes.Structure):
        _fields_=[("length",ctypes.c_ulong),("load",ctypes.c_ulong),
                  ("total_physical",ctypes.c_ulonglong),("available_physical",ctypes.c_ulonglong),
                  ("total_page_file",ctypes.c_ulonglong),("available_page_file",ctypes.c_ulonglong),
                  ("total_virtual",ctypes.c_ulonglong),("available_virtual",ctypes.c_ulonglong),
                  ("available_extended_virtual",ctypes.c_ulonglong)]
    status=MemoryStatus()
    status.length=ctypes.sizeof(status)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        hardware.update(ram_mb=status.total_physical/2**20,free_ram_mb=status.available_physical/2**20)
url=args.base_url+"/api/v1/recommendations?limit=10"
for _ in range(20):
    with opener.open(url,timeout=30) as response:
        warm=json.load(response)
cookie="; ".join(c.name+"="+c.value for c in jar)
def request(_):
    start=time.perf_counter()
    try:
        req=urllib.request.Request(url,headers={"Cookie":cookie})
        with urllib.request.urlopen(req,timeout=30) as response:
            data=json.load(response)
            assert len(data["items"])>0
        return (time.perf_counter()-start)*1000,data,None
    except Exception as error:
        return (time.perf_counter()-start)*1000,None,type(error).__name__+": "+str(error)
start=time.perf_counter()
with ThreadPoolExecutor(max_workers=args.clients) as pool:
    results=list(pool.map(request,range(args.requests)))
elapsed=time.perf_counter()-start
times=sorted(r[0] for r in results)
report={"measured_at":datetime.now(timezone.utc).isoformat(),"profile":"demo",
        "boundary":"HTTP "+args.base_url+" -> Next production proxy -> FastAPI -> PostgreSQL/Redis",
        "url":url,"catalog_size":catalog_size,"hardware":hardware,"workload":"one stable guest actor; repeated limit=10; cached path after warmup",
        "request_ids":[r[1]["request_id"] for r in results if r[1]],"warmup":20,"requests":args.requests,"clients":args.clients,"seconds":elapsed,
        "p50_ms":statistics.median(times),"p95_ms":times[int(.95*(len(times)-1))],
        "throughput_rps":args.requests/elapsed,"errors":[r[2] for r in results if r[2]],
        "model_versions":sorted({r[1]["model_version"] for r in results if r[1]}),
        "target_p95_ms":300,"target_met":times[int(.95*(len(times)-1))]<300}
Path("docs/evidence/compose-http-benchmark.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({k:v for k,v in report.items() if k!="request_ids"},indent=2))
if report["errors"]:
    raise SystemExit(1)
