"""Register a trusted local experiment report and compatible copied bundles; never promote."""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from atlasrec_api.db import SessionLocal
from atlasrec_api.lifecycle import register_report
from atlasrec_api.settings import settings

parser=argparse.ArgumentParser()
parser.add_argument("report")
parser.add_argument("--bundle-root",default=str(settings.artifact_dir))
args=parser.parse_args()
report=json.loads(Path(args.report).read_text(encoding="utf-8"))
if report["manifest"]["profile"] != settings.profile:
    raise SystemExit("Report profile must match this installation")
for record in report["runs"]:
    if not re.fullmatch(r"[a-z_]+-[a-f0-9]{12}",record["id"]):
        raise SystemExit("Unexpected bundle identifier")
    if record["status"]=="completed":
        record["original_bundle_location"]=record["bundle"]
        record["bundle"]=str(Path(args.bundle_root).resolve()/record["id"])
        record["registered_at"]=datetime.now(timezone.utc).isoformat()
with SessionLocal() as db:
    register_report(db,report)
print("Registered",len(report["runs"]),"actual runs; active model preserved")
