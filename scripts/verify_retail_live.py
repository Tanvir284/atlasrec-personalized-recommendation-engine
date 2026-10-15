"""Verify real inference and a queued worker job; remove only declared QA accounts first."""
import argparse
import http.cookiejar
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from atlasrec_api.db import Event, Favorite, RecommendationRequest, Session, SessionLocal, User
from atlasrec_api.lifecycle import active_bundle
from atlasrec_api.settings import settings
from sqlalchemy import delete, select


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--qa-accounts")
    parser.add_argument("--cleanup-only", action="store_true")
    args = parser.parse_args()
    removed = 0
    with SessionLocal() as db:
        if args.qa_accounts:
            for line in Path(args.qa_accounts).read_text().splitlines():
                email = json.loads(line)["email"]
                if not re.fullmatch(r"retail-qa-\d+-(desktop|phone)@example\.test", email):
                    raise ValueError("Refusing to clean an account outside the declared QA namespace")
                user = db.scalar(select(User).where(User.email == email, User.name == "AtlasRec verification", User.admin.is_(False)))
                if not user:
                    continue
                for table in (Session, Event, Favorite, RecommendationRequest):
                    db.execute(delete(table).where(table.user_id == user.id))
                db.delete(user)
                removed += 1
            db.commit()
        if args.cleanup_only:
            print(json.dumps({"qa_accounts_removed": removed}))
            return
        model, version = active_bundle(db)
        assert model and settings.profile == "research"
        histories = [[model.f.ids[i] for i in dict.fromkeys(history)][:8]
                     for history in model.f.histories.values() if len(set(history)) >= 3]
        first = model.recommend(None, histories[0])[0]
        different = next((history for history in histories[1:100]
                          if model.recommend(None, history)[0] != first), None)
        assert different, "Different observed histories must change personalized predictions"
        second = model.recommend(None, different)[0]
        assert not (set(first) & set(histories[0]))
        assert not (set(second) & set(different))
        assert all(not item.startswith("demo-") for item in first + second)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    csrf = None

    def api(path, payload=None):
        headers = {"Origin": "http://localhost:3000"}
        if payload is not None:
            headers.update({"Content-Type": "application/json", "X-CSRF-Token": csrf})
        request = urllib.request.Request("http://127.0.0.1:8000/api/v1" + path,
                                         data=json.dumps(payload).encode() if payload is not None else None,
                                         headers=headers)
        with opener.open(request, timeout=45) as response:
            return json.load(response)

    info = api("/catalog/info")
    assert not info["synthetic"] and info["personalization"]["status"] == "ready"
    csrf = api("/auth/csrf")["csrf_token"]
    csrf = api("/auth/login", {"email": settings.demo_admin_email,
                               "password": settings.demo_admin_password})["csrf_token"]
    started = time.monotonic()
    queued = api("/admin/jobs", {"model": "item_cf", "epochs": 2, "include_application_feedback": True})
    assert queued["status"] == "queued", queued
    print("Queued real-data worker job", queued["id"], flush=True)
    while time.monotonic() - started < 420:
        job = next(row for row in api("/admin/jobs") if row["id"] == queued["id"])
        if job["status"] in ("completed", "failed"):
            break
        time.sleep(5)
    assert job["status"] == "completed", job.get("error") or job["status"]
    assert api("/catalog/info")["personalization"]["active_model_version"] == version
    evidence = {"checked_at": datetime.now(timezone.utc).isoformat(), "status": "passed", "catalog": info,
                "inference": {"actual_model": version, "distinct_histories_change_predictions": True,
                              "observed_items_excluded": True, "first_prediction": first, "second_prediction": second},
                "qa_accounts_removed_before_training": removed,
                "worker": {"job_id": job["id"], "status": job["status"], "runs": job["result"]["runs"],
                           "seconds": round(time.monotonic() - started, 2), "active_model_preserved": True}}
    destination = settings.artifact_dir / "retail-live-checks.json"
    destination.write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
