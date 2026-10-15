"""Protected ML workbench: datasets, experiments, model registry, jobs and monitoring."""
import uuid
from collections import Counter

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, func, select, update

from ..common import bump_history, mutation, user_json
from ..db import (
    Audit,
    DatasetVersion,
    Event,
    Favorite,
    Job,
    ModelVersion,
    Product,
    RecommendationRequest,
    Run,
    Session,
    User,
    db_session,
    now,
)
from ..lifecycle import promote
from ..monitoring import observed_errors
from ..queue import celery
from ..research import training_snapshot
from ..schemas import AdminUserCreate, AdminUserUpdate, Training
from ..security import hasher, require_admin
from ..settings import settings
from .health import ready

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

STALE_JOB_GRACE_SECONDS = 180


def _job_is_stale(job):
    updated = job.updated_at
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=now().tzinfo)
    return job.status == "running" and (now() - updated).total_seconds() > settings.train_time_budget + STALE_JOB_GRACE_SECONDS


def _enqueue(db, job, failure_message):
    try:
        celery.send_task("atlasrec.train", args=[job.id], task_id=job.id)
    except Exception:
        job.status, job.error = "failed", failure_message
        db.commit()


@router.get("/overview")
def overview(request: Request, db=Depends(db_session)):
    require_admin(request, db)
    counts = {
        "products": db.scalar(select(func.count()).select_from(Product).where(
            Product.profile == settings.profile, Product.available.is_(True))),
        "users": db.scalar(select(func.count()).select_from(User)),
        "runs": db.scalar(select(func.count()).select_from(Run).where(Run.profile == settings.profile)),
        "jobs": db.scalar(select(func.count()).select_from(Job)),
    }
    pending = db.scalar(select(func.count()).select_from(Job).where(Job.status.in_(["queued", "running"])))
    return {**counts, "profile": settings.profile, "synthetic": settings.profile == "demo",
            "health": ready(db), "pending_jobs": pending}


@router.get("/users")
def list_users(request: Request, db=Depends(db_session)):
    require_admin(request, db)
    users = db.scalars(select(User).order_by(User.created_at.desc(), User.email.asc())).all()
    fav_counts = dict(
        db.execute(
            select(Favorite.user_id, func.count())
            .join(Product, Favorite.item_id == Product.id)
            .where(Product.profile == settings.profile)
            .group_by(Favorite.user_id)
        ).all()
    )
    event_counts = dict(
        db.execute(
            select(Event.user_id, func.count())
            .where(Event.user_id.is_not(None), Event.profile == settings.profile, Event.kind != "impression")
            .group_by(Event.user_id)
        ).all()
    )
    rating_counts = dict(
        db.execute(
            select(Event.user_id, func.count())
            .where(Event.user_id.is_not(None), Event.profile == settings.profile, Event.kind == "rating")
            .group_by(Event.user_id)
        ).all()
    )
    session_counts = dict(
        db.execute(
            select(Session.user_id, func.count())
            .where(Session.expires_at > now())
            .group_by(Session.user_id)
        ).all()
    )
    items = []
    for u in users:
        row = user_json(u)
        row["favorites_count"] = int(fav_counts.get(u.id, 0))
        row["events_count"] = int(event_counts.get(u.id, 0))
        row["ratings_count"] = int(rating_counts.get(u.id, 0))
        row["sessions_count"] = int(session_counts.get(u.id, 0))
        items.append(row)
    return {
        "items": items,
        "summary": {
            "total": len(items),
            "admins": sum(1 for u in items if u["admin"]),
            "with_preferences": sum(1 for u in items if u["preferences"]),
            "active_sessions": sum(u["sessions_count"] for u in items),
        },
    }


@router.post("/users", dependencies=[Depends(mutation)])
def create_user(body: AdminUserCreate, request: Request, db=Depends(db_session)):
    admin = require_admin(request, db)
    email = body.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        name=body.name.strip(),
        password_hash=hasher.hash(body.password),
        admin=bool(body.admin),
        preferences=[],
    )
    db.add(user)
    db.add(Audit(id=str(uuid.uuid4()), actor_id=admin.id, action="user_create",
                 details={"user_id": user.id, "email": user.email, "admin": user.admin}))
    db.commit()
    return {"user": user_json(user)}


@router.patch("/users/{user_id}", dependencies=[Depends(mutation)])
def update_user(user_id: str, body: AdminUserUpdate, request: Request, db=Depends(db_session)):
    admin = require_admin(request, db)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if body.name is not None:
        user.name = body.name
    if body.email is not None and body.email != user.email:
        if db.scalar(select(User).where(User.email == body.email, User.id != user.id)):
            raise HTTPException(409, "Email already registered")
        user.email = body.email
    if body.admin is not None:
        user.admin = bool(body.admin)
    if body.password is not None:
        user.password_hash = hasher.hash(body.password)
    if body.preferences is not None:
        user.preferences = list(dict.fromkeys(c.strip() for c in body.preferences if c.strip()))
        bump_history(db, user)
    db.add(Audit(id=str(uuid.uuid4()), actor_id=admin.id, action="user_update",
                 details={"user_id": user.id, "email": user.email, "name": user.name, "admin": user.admin}))
    db.commit()
    return {"user": user_json(user)}


@router.delete("/users/{user_id}/history", dependencies=[Depends(mutation)])
def clear_user_history(user_id: str, request: Request, db=Depends(db_session)):
    require_admin(request, db)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    profile_items = select(Product.id).where(Product.profile == settings.profile)
    db.execute(delete(Event).where(Event.user_id == user.id, Event.profile == settings.profile))
    db.execute(delete(Favorite).where(Favorite.user_id == user.id, Favorite.item_id.in_(profile_items)))
    bump_history(db, user)
    db.commit()
    return {"ok": True}


@router.delete("/users/{user_id}", dependencies=[Depends(mutation)])
def delete_user(user_id: str, request: Request, db=Depends(db_session)):
    admin = require_admin(request, db)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == admin.id:
        raise HTTPException(422, "Cannot delete your own active administrator account")
    db.execute(delete(Session).where(Session.user_id == user.id))
    db.execute(delete(Favorite).where(Favorite.user_id == user.id))
    db.execute(delete(Event).where(Event.user_id == user.id))
    db.execute(delete(Job).where(Job.user_id == user.id))
    db.execute(delete(Audit).where(Audit.actor_id == user.id))
    db.execute(update(RecommendationRequest).where(RecommendationRequest.user_id == user.id).values(user_id=None))
    db.delete(user)
    db.commit()
    return {"ok": True}


@router.get("/datasets")
def datasets(request: Request, db=Depends(db_session)):
    require_admin(request, db)
    rows = db.scalars(select(DatasetVersion).where(DatasetVersion.profile == settings.profile)).all()
    return [{"id": d.id, "profile": d.profile, "manifest": d.manifest} for d in rows]


@router.get("/experiments")
def experiments(request: Request, include_user_rows: bool = False, db=Depends(db_session)):
    require_admin(request, db)
    rows = db.scalars(select(Run).where(Run.profile == settings.profile).order_by(Run.created_at.desc()).limit(100)).all()
    records = []
    for row in rows:
        record = {**row.record, "created_at": row.created_at.isoformat()}
        if not include_user_rows:
            for key in ("metrics", "validation", "diversity_metrics"):
                if isinstance(record.get(key), dict):
                    record[key] = {name: value for name, value in record[key].items() if name != "user_rows"}
        records.append(record)
    return records


@router.get("/models")
def models(request: Request, db=Depends(db_session)):
    require_admin(request, db)
    rows = db.scalars(select(ModelVersion).where(ModelVersion.profile == settings.profile)
                      .order_by(ModelVersion.created_at.desc())).all()
    known_ids = {version.id for version in rows}
    audits = [audit for audit in db.scalars(select(Audit).order_by(Audit.created_at.desc())).all()
              if audit.details.get("profile", settings.profile) == settings.profile and
              audit.details.get("next") in known_ids][:30]
    return {"items": [{"id": v.id, "validated": v.validated, "active": v.active, "run_id": v.run_id} for v in rows],
            "history": [{"action": a.action, "details": a.details, "at": a.created_at.isoformat()} for a in audits]}


@router.post("/models/{version}/promote", dependencies=[Depends(mutation)])
def promote_model(version: str, request: Request, db=Depends(db_session)):
    admin = require_admin(request, db)
    try:
        promote(db, version, admin.id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"active": version}


@router.post("/models/rollback", dependencies=[Depends(mutation)])
def rollback(request: Request, db=Depends(db_session)):
    admin = require_admin(request, db)
    audits = db.scalars(select(Audit).where(Audit.action.in_(["promote", "rollback"])).order_by(Audit.created_at.desc())).all()
    for audit in audits:
        if audit.details.get("profile", settings.profile) != settings.profile:
            continue
        for previous_id in audit.details.get("previous", []):
            previous = db.get(ModelVersion, previous_id)
            if not previous or previous.profile != settings.profile or not previous.validated or previous.active:
                continue
            try:
                promote(db, previous_id, admin.id, "rollback")
            except (ValueError, FileNotFoundError) as exc:
                raise HTTPException(422, str(exc)) from exc
            return {"active": previous_id}
    raise HTTPException(422, "No previous validated version")


@router.get("/jobs")
def jobs(request: Request, db=Depends(db_session)):
    require_admin(request, db)
    rows = db.scalars(select(Job).order_by(Job.created_at.desc()).limit(100)).all()
    return [{"id": j.id, "status": j.status, "progress": j.progress, "config": j.config,
             "error": j.error, "attempts": j.attempts,
             "retryable": j.status == "failed" or _job_is_stale(j),
             "result": j.result, "updated_at": j.updated_at.isoformat()} for j in rows]


@router.post("/jobs", dependencies=[Depends(mutation)], status_code=202)
def start_job(body: Training, request: Request, db=Depends(db_session)):
    admin = require_admin(request, db)
    config = {"profile": settings.profile, "models": [body.model], "epochs": body.epochs,
              "seed": body.seed, "threads": settings.train_threads,
              "time_budget": settings.train_time_budget, "cold_item_fraction": 0}
    if settings.profile == "research":
        try:
            config.update(training_snapshot(db, body.include_application_feedback))
        except (ValueError, OSError, KeyError) as exc:
            raise HTTPException(422, str(exc)) from None
        config["refit_for_serving"] = True
        config["include_application_feedback"] = body.include_application_feedback
    job = Job(id=str(uuid.uuid4()), user_id=admin.id, status="queued", progress=0, config=config)
    db.add(job)
    db.commit()
    _enqueue(db, job, "Queue unavailable; start Redis/worker, then retry.")
    return {"id": job.id, "status": job.status}


@router.post("/jobs/{job_id}/retry", dependencies=[Depends(mutation)], status_code=202)
def retry_job(job_id: str, request: Request, db=Depends(db_session)):
    require_admin(request, db)
    job = db.get(Job, job_id)
    if not job or (job.status != "failed" and not _job_is_stale(job)):
        raise HTTPException(422, "Only failed or expired worker jobs can be retried")
    job.status, job.progress, job.error = "queued", 0, None
    db.commit()
    _enqueue(db, job, "Queue remains unavailable")
    return {"id": job.id, "status": job.status}


def _category_distribution(rows, categories):
    counts = Counter(categories[e.item_id] for e in rows if e.item_id in categories)
    return {k: v / max(1, len(rows)) for k, v in counts.items()}


@router.get("/monitoring")
def monitoring(request: Request, db=Depends(db_session)):
    require_admin(request, db)
    rows = db.scalars(select(RecommendationRequest).where(RecommendationRequest.profile == settings.profile)
                      .order_by(RecommendationRequest.created_at.desc()).limit(1000)).all()
    latencies = [r.duration_ms for r in rows]
    event_query = select(Event).where(Event.profile == settings.profile)
    count = db.scalar(select(func.count()).select_from(Event).where(Event.profile == settings.profile))
    reference = db.scalars(event_query.order_by(Event.created_at, Event.id).limit(settings.drift_window)).all()
    current = db.scalars(event_query.order_by(Event.created_at.desc(), Event.id.desc()).limit(settings.drift_window)).all()
    catalog = db.execute(select(Product.id, Product.category, Product.price).where(Product.profile == settings.profile)).all()
    categories = {item_id: category for item_id, category, _ in catalog}
    missing_prices = sum(price is None for _, _, price in catalog)

    a, b = _category_distribution(reference, categories), _category_distribution(current, categories)
    tv = 0.5 * sum(abs(a.get(k, 0) - b.get(k, 0)) for k in a.keys() | b.keys())
    ref_numeric = [e.position for e in reference if e.position is not None]
    cur_numeric = [e.position for e in current if e.position is not None]
    shift = (abs(float(np.mean(cur_numeric) - np.mean(ref_numeric))) / max(float(np.std(ref_numeric)), 1)
             if ref_numeric and cur_numeric else None)
    enough = count >= 2 * settings.drift_window
    numeric_enough = enough and min(len(ref_numeric), len(cur_numeric)) >= settings.drift_numeric_min_samples
    return {"profile": settings.profile, "window": "last 1000 recommendation requests",
            "requests": len(rows), "p50_ms": float(np.quantile(latencies, 0.5)) if rows else None,
            "p95_ms": float(np.quantile(latencies, 0.95)) if rows else None,
            "cache_hit_rate": sum(r.cache_hit for r in rows) / len(rows) if rows else None,
            "fallback_rate": sum(r.fallback is not None for r in rows) / len(rows) if rows else None,
            "errors_since_process_start": dict(observed_errors),
            "feature_missingness": missing_prices / max(1, len(catalog)),
            "drift": {"reference": f"earliest {settings.drift_window} observed events",
                      "current": f"latest {settings.drift_window} observed events",
                      "reference_n": len(reference), "current_n": len(current), "sufficient_nonoverlap": enough,
                      "category_total_variation": tv if enough else None,
                      "threshold": settings.drift_category_threshold,
                      "category_warning": bool(enough and tv > settings.drift_category_threshold),
                      "position_standardized_mean_shift": shift if numeric_enough else None,
                      "numeric_threshold": settings.drift_numeric_threshold,
                      "numeric_warning": bool(numeric_enough and shift > settings.drift_numeric_threshold),
                      "numeric_min_samples": settings.drift_numeric_min_samples,
                      "numeric_reference_n": len(ref_numeric), "numeric_current_n": len(cur_numeric)},
            "fallback_reasons": dict(Counter(r.fallback for r in rows if r.fallback))}
