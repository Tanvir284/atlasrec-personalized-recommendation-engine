"""Application entry point: builds the FastAPI app, installs middleware, mounts routers.

Domain logic lives in ``routers/``; this module only wires things together. A few names
are re-exported for scripts and tests that historically imported them from here.
"""
from __future__ import annotations

import json
import time
import uuid

from fastapi import FastAPI, Request, Response
from sqlalchemy.exc import SQLAlchemyError

from .lifecycle import active_bundle
from .monitoring import log, observed_errors
from .queue import celery
from .ratelimit import local_attempts as rate_attempts
from .routers import account, admin, auth, catalog, events, health, recommendations
from .routers.recommendations import allowed_history

__all__ = ["app", "active_bundle", "allowed_history", "celery", "observed_errors", "rate_attempts"]

MAX_BODY_BYTES = 1024 * 1024

app = FastAPI(title="AtlasRec", version="0.1.0", openapi_url="/api/v1/openapi.json")


def _error(detail, request_id, status_code):
    return Response(json.dumps({"detail": detail, "request_id": request_id}),
                    status_code=status_code, media_type="application/json")


@app.middleware("http")
async def request_monitor(request: Request, call_next):
    """Body-size guard, structured access log, error envelope and request id header."""
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    try:
        if int(request.headers.get("content-length", "0")) > MAX_BODY_BYTES:
            return Response("Request too large", status_code=413)
        if request.method in ("POST", "PUT", "PATCH"):
            if len(await request.body()) > MAX_BODY_BYTES:
                return Response("Request too large", status_code=413)
        response = await call_next(request)
    except SQLAlchemyError:
        observed_errors["database"] += 1
        response = _error("Database unavailable", request_id, 503)
    except Exception as exc:
        observed_errors[type(exc).__name__] += 1
        log.error(json.dumps({"request_id": request_id, "error_type": type(exc).__name__}))
        response = _error("Service error", request_id, 500)
    if response.status_code >= 400:
        observed_errors[str(response.status_code)] += 1
    response.headers["x-request-id"] = request_id
    response.headers["x-content-type-options"] = "nosniff"
    log.info(json.dumps({"request_id": request_id, "path": request.url.path,
                         "status": response.status_code, "duration_ms": (time.perf_counter() - start) * 1000}))
    return response


for module in (health, auth, account, catalog, events, recommendations, admin):
    app.include_router(module.router)
