"""Liveness and readiness probes used by Compose health checks."""
from fastapi import APIRouter, Depends
from sqlalchemy import text

from ..db import db_session
from ..lifecycle import active_bundle
from ..settings import settings

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live():
    return {"status": "alive", "profile": settings.profile}


@router.get("/health/ready")
def ready(db=Depends(db_session)):
    db.execute(text("SELECT 1"))
    try:
        model, version = active_bundle(db)
        model_state = "ready" if model else "fallback"
    except Exception:
        version, model_state = None, "invalid"
    return {"database": "ready", "model": model_state, "model_version": version}
