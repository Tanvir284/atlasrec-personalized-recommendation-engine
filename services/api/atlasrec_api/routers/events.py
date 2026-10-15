"""Idempotent shopper feedback events (views, impressions, clicks, dismissals, ratings)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..common import actor_key, bump_history, lookup_product, mutation
from ..db import Event, RecommendationRequest, db_session, now
from ..schemas import Feedback
from ..security import current_user
from ..settings import settings

router = APIRouter(prefix="/api/v1", tags=["events"])

EXPOSURE_KINDS = ("view", "impression", "click")


def event_matches(existing, body, actor):
    """True when a stored event is an exact replay of ``body`` (safe retry after a lost response)."""
    return (existing.actor_key == actor and existing.item_id == body.item_id and
            existing.kind == body.kind and existing.rating == body.rating and
            existing.surface == body.surface and
            existing.request_id == (str(body.request_id) if body.request_id else None) and
            (body.position is None or existing.position == body.position) and
            (existing.client_timestamp.isoformat().replace("+00:00", "") if existing.client_timestamp else None) ==
            (body.client_timestamp.astimezone(now().tzinfo).replace(tzinfo=None).isoformat() if body.client_timestamp else None))


def _find_exposure(db, rec_id, item_id, kind):
    return db.scalar(select(Event).where(Event.request_id == rec_id, Event.item_id == item_id, Event.kind == kind))


@router.post("/events", dependencies=[Depends(mutation)])
def events(body: Feedback, request: Request, db=Depends(db_session)):
    user = current_user(request, db)
    lookup_product(db, body.item_id)
    if body.kind in ("dismiss", "rating") and not user:
        raise HTTPException(401, "Sign in to send this feedback")
    actor = actor_key(request, user)
    if not actor:
        raise HTTPException(401, "Initialize your browsing session with recommendations")
    client_ts = body.client_timestamp
    if client_ts and (client_ts.tzinfo is None or abs((now() - client_ts).total_seconds()) > 86400):
        raise HTTPException(422, "Client timestamp must be UTC-aware and within one day")
    existing = db.get(Event, str(body.id))
    if existing:
        if not event_matches(existing, body, actor):
            raise HTTPException(409, "Event ID already used")
        return {"ok": True, "duplicate": True}
    rec_id = str(body.request_id) if body.request_id else None
    rec = db.get(RecommendationRequest, rec_id) if rec_id else None
    if (rec_id and not rec) or (body.kind == "impression" and not rec):
        raise HTTPException(422, "A valid recommendation request is required")
    if body.position is not None and not rec:
        raise HTTPException(422, "Served positions require a recommendation request")
    position = body.position
    if rec:
        if rec.actor_key != actor or rec.profile != settings.profile:
            raise HTTPException(403, "Recommendation ownership mismatch")
        if body.item_id not in rec.item_ids:
            raise HTTPException(422, "Item was not served for this request")
        served_position = rec.item_ids.index(body.item_id)
        if position is not None and served_position != position:
            raise HTTPException(422, "Incorrect served position")
        position = served_position
        if body.kind in EXPOSURE_KINDS and _find_exposure(db, rec_id, body.item_id, body.kind):
            return {"ok": True, "duplicate": True}
    db.add(Event(id=str(body.id), user_id=user.id if user else None, item_id=body.item_id,
                 actor_key=actor, rating=body.rating, kind=body.kind, profile=settings.profile, surface=body.surface,
                 request_id=rec_id, position=position,
                 model_version=rec.model_version if rec else None, client_timestamp=client_ts))
    try:
        if user and body.kind in ("view", "click", "dismiss", "rating"):
            bump_history(db, user)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(Event, str(body.id))
        if existing and event_matches(existing, body, actor):
            return {"ok": True, "duplicate": True}
        if not existing and rec_id and body.kind in EXPOSURE_KINDS:
            existing = _find_exposure(db, rec_id, body.item_id, body.kind)
            if existing and existing.actor_key == actor:
                return {"ok": True, "duplicate": True}
        raise HTTPException(409, "Event ID already used") from None
    return {"ok": True, "duplicate": False}
