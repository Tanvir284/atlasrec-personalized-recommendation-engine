"""Verify the measured HTTP request IDs against PostgreSQL, including Redis cache hits."""
import argparse
import json
from pathlib import Path

from atlasrec_api.db import RecommendationRequest, SessionLocal
from atlasrec_api.settings import settings
from sqlalchemy import select

parser=argparse.ArgumentParser()
parser.add_argument("report")
parser.add_argument("--output")
args=parser.parse_args()
path=Path(args.report)
report=json.loads(path.read_text(encoding="utf-8"))
assert report["profile"]==settings.profile
with SessionLocal() as db:
    rows=db.scalars(select(RecommendationRequest).where(
        RecommendationRequest.id.in_(report["request_ids"]),
        RecommendationRequest.profile==settings.profile)).all()
assert len(rows)==report["requests"] and not report["errors"]
report["stored_requests"]=len(rows)
report["cache_hit_requests"]=sum(r.cache_hit for r in rows)
report["cache_hit_rate"]=report["cache_hit_requests"]/len(rows)
report["cache_state"]="verified per-request PostgreSQL records; Redis configured"
Path(args.output or args.report).write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps({k:v for k,v in report.items() if k!="request_ids"},indent=2))
