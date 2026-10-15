from atlasrec_ml.pipeline import run
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select

from .db import Job, SessionLocal
from .lifecycle import register_report
from .queue import celery
from .research import load_snapshot
from .settings import settings


@celery.task(name="atlasrec.train")
def train_job(job_id):
    with SessionLocal() as db:
        # Read the current state under the lock rather than reusing a cached ORM row.
        job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if not job or job.status == "completed":
            return {"idempotent": True}
        if job.status == "running":
            return {"already_running": True}
        job.status, job.progress, job.attempts = "running", 0.05, job.attempts + 1
        db.commit()
        try:
            def progress(value):
                job.progress = min(0.9, 0.05 + value * 0.8)
                db.commit()
            if job.config.get("profile", "demo") != settings.profile:
                raise ValueError("Training job profile differs from this worker")
            data = load_snapshot(job.config) if settings.profile == "research" else None
            report = run(job.config, data=data, progress=progress)
            register_report(db, report)
            failed = [r for r in report["runs"] if r["status"] != "completed"]
            if failed:
                raise ValueError(failed[0].get("error", failed[0]["status"]))
            job.status, job.progress = "completed", 1
            job.result = {"runs": [r["id"] for r in report["runs"]]}
        except (Exception, SoftTimeLimitExceeded) as exc:
            db.rollback()
            job = db.get(Job, job_id)
            job.status, job.error = "failed", str(exc)[:1000]
        db.commit()
        return {"id": job_id, "status": job.status}
