"""The signed-in shopper's profile, preferences, history, security and saved products."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..common import bump_history, lookup_product, mutation, product_json, user_json
from ..db import (
    Audit,
    Event,
    Favorite,
    Job,
    Product,
    RecommendationRequest,
    Session,
    User,
    db_session,
    now,
)
from ..schemas import PasswordChange, Preferences, ProfileUpdate
from ..security import current_session, current_user, hasher, verify_password
from ..settings import settings

router = APIRouter(prefix="/api/v1", tags=["account"])


def _user_stats(db, user_id: str) -> dict:
    fav_count = db.scalar(
        select(func.count())
        .select_from(Favorite)
        .join(Product, Favorite.item_id == Product.id)
        .where(Favorite.user_id == user_id, Product.profile == settings.profile)
    ) or 0
    events_count = db.scalar(
        select(func.count())
        .select_from(Event)
        .where(Event.user_id == user_id, Event.profile == settings.profile, Event.kind != "impression")
    ) or 0
    ratings_count = db.scalar(
        select(func.count())
        .select_from(Event)
        .where(Event.user_id == user_id, Event.profile == settings.profile, Event.kind == "rating")
    ) or 0
    sessions_count = db.scalar(
        select(func.count())
        .select_from(Session)
        .where(Session.user_id == user_id, Session.expires_at > now())
    ) or 0
    return {
        "favorites_count": int(fav_count),
        "events_count": int(events_count),
        "ratings_count": int(ratings_count),
        "sessions_count": int(sessions_count),
    }


@router.get("/me")
def me(request: Request, db=Depends(db_session)):
    user = current_user(request, db)
    payload = user_json(user) if user else None
    if payload and user:
        payload["stats"] = _user_stats(db, user.id)
    return {"user": payload, "profile": settings.profile}


@router.patch("/me", dependencies=[Depends(mutation)])
def update_me(body: ProfileUpdate, request: Request, db=Depends(db_session)):
    user = current_user(request, db, True)
    if body.name is not None:
        user.name = body.name
    if body.email is not None and body.email != user.email:
        existing = db.scalar(select(User).where(User.email == body.email, User.id != user.id))
        if existing:
            raise HTTPException(409, "Email already registered")
        user.email = body.email
    if body.admin is not None:
        user.admin = bool(body.admin)
    if body.password is not None:
        user.password_hash = hasher.hash(body.password)
    if body.preferences is not None:
        user.preferences = list(dict.fromkeys(c.strip() for c in body.preferences if c.strip()))
        bump_history(db, user)
    db.commit()
    payload = user_json(user)
    payload["stats"] = _user_stats(db, user.id)
    return {"user": payload}


@router.post("/me/password", dependencies=[Depends(mutation)])
def change_password(body: PasswordChange, request: Request, db=Depends(db_session)):
    user = current_user(request, db, True)
    if body.current_password and not verify_password(user.password_hash, body.current_password):
        raise HTTPException(401, "Current password is incorrect")
    user.password_hash = hasher.hash(body.new_password)
    db.commit()
    return {"ok": True}


@router.get("/me/sessions")
def list_sessions(request: Request, db=Depends(db_session)):
    user = current_user(request, db, True)
    cur = current_session(request, db)
    rows = db.scalars(
        select(Session)
        .where(Session.user_id == user.id, Session.expires_at > now())
        .order_by(Session.expires_at.desc())
    ).all()
    return {
        "items": [
            {
                "id": s.token_hash[:12],
                "expires_at": s.expires_at.isoformat(),
                "current": bool(cur and s.token_hash == cur.token_hash),
            }
            for s in rows
        ]
    }


@router.delete("/me/sessions/{session_id}", dependencies=[Depends(mutation)])
def revoke_session(session_id: str, request: Request, db=Depends(db_session)):
    user = current_user(request, db, True)
    cur = current_session(request, db)
    rows = db.scalars(select(Session).where(Session.user_id == user.id)).all()
    removed = 0
    for s in rows:
        is_current = bool(cur and s.token_hash == cur.token_hash)
        if session_id == "others" and not is_current:
            db.delete(s)
            removed += 1
        elif session_id != "others" and s.token_hash[:12] == session_id and not is_current:
            db.delete(s)
            removed += 1
    db.commit()
    return {"ok": True, "removed": removed}


@router.delete("/me", dependencies=[Depends(mutation)])
def delete_me(request: Request, response: Response, db=Depends(db_session)):
    user = current_user(request, db, True)
    db.execute(delete(Session).where(Session.user_id == user.id))
    db.execute(delete(Favorite).where(Favorite.user_id == user.id))
    db.execute(delete(Event).where(Event.user_id == user.id))
    db.execute(delete(Job).where(Job.user_id == user.id))
    db.execute(delete(Audit).where(Audit.actor_id == user.id))
    db.execute(update(RecommendationRequest).where(RecommendationRequest.user_id == user.id).values(user_id=None))
    db.delete(user)
    db.commit()
    response.delete_cookie("atlas_session", path="/")
    response.delete_cookie("atlas_csrf", path="/")
    return {"ok": True}


@router.put("/me/preferences", dependencies=[Depends(mutation)])
def preferences(body: Preferences, request: Request, db=Depends(db_session)):
    user = current_user(request, db, True)
    allowed = set(db.scalars(select(Product.category).where(Product.profile == settings.profile).distinct()).all())
    if set(body.categories) - allowed:
        raise HTTPException(422, "Unknown interest category")
    user.preferences = list(dict.fromkeys(body.categories))
    bump_history(db, user)
    db.commit()
    return user_json(user)


@router.get("/me/history")
def history(request: Request, item_id: str | None = Query(None, max_length=200),
            ratings_only: bool = False, db=Depends(db_session)):
    user = current_user(request, db, True)
    statement = select(Event).where(Event.user_id == user.id, Event.profile == settings.profile)
    if item_id is not None:
        statement = statement.where(Event.item_id == item_id)
    if ratings_only:
        statement = statement.where(Event.kind == "rating")
    rows = db.scalars(statement.order_by(Event.created_at.desc(), Event.id.desc()).limit(100)).all()
    item_ids = {e.item_id for e in rows}
    titles = dict(db.execute(select(Product.id, Product.title).where(Product.id.in_(item_ids))).all()) if item_ids else {}
    return [{"id": e.id, "item_id": e.item_id, "title": titles.get(e.item_id), "kind": e.kind,
             "rating": e.rating, "timestamp": e.created_at.isoformat()} for e in rows]


@router.delete("/me/history/{event_id}", dependencies=[Depends(mutation)])
def delete_history_event(event_id: str, request: Request, db=Depends(db_session)):
    user = current_user(request, db, True)
    removed = db.execute(
        delete(Event).where(Event.id == event_id, Event.user_id == user.id, Event.profile == settings.profile)
    )
    if removed.rowcount:
        bump_history(db, user)
        db.commit()
    return {"ok": True}


@router.delete("/me/history", dependencies=[Depends(mutation)])
def clear_history(request: Request, db=Depends(db_session)):
    user = current_user(request, db, True)
    profile_items = select(Product.id).where(Product.profile == settings.profile)
    db.execute(delete(Event).where(Event.user_id == user.id, Event.profile == settings.profile))
    db.execute(delete(Favorite).where(Favorite.user_id == user.id, Favorite.item_id.in_(profile_items)))
    bump_history(db, user)
    db.commit()
    return {"ok": True}


@router.get("/favorites")
def favorites(request: Request, db=Depends(db_session)):
    user = current_user(request, db, True)
    rows = db.scalars(select(Product).join(Favorite, Favorite.item_id == Product.id)
                      .where(Favorite.user_id == user.id, Product.profile == settings.profile)
                      .order_by(Favorite.created_at.desc(), Product.id.asc())).all()
    return {"items": [product_json(p) for p in rows]}


@router.put("/favorites/{item_id}", dependencies=[Depends(mutation)])
def add_favorite(item_id: str, request: Request, db=Depends(db_session)):
    user = current_user(request, db, True)
    lookup_product(db, item_id)
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    created = db.scalar(insert(Favorite).values(user_id=user.id, item_id=item_id)
                        .on_conflict_do_nothing(index_elements=["user_id", "item_id"])
                        .returning(Favorite.item_id))
    if created:
        bump_history(db, user)
        db.add(Event(id=str(uuid.uuid4()), user_id=user.id, actor_key="u:" + user.id,
                     item_id=item_id, kind="favorite", surface="saved", profile=settings.profile))
    db.commit()
    return {"ok": True}


@router.delete("/favorites/{item_id}", dependencies=[Depends(mutation)])
def remove_favorite(item_id: str, request: Request, db=Depends(db_session)):
    user = current_user(request, db, True)
    removed = db.execute(delete(Favorite).where(Favorite.user_id == user.id, Favorite.item_id == item_id))
    if removed.rowcount:
        db.execute(delete(Event).where(Event.user_id == user.id, Event.item_id == item_id,
                                       Event.kind == "favorite", Event.profile == settings.profile))
        bump_history(db, user)
    db.commit()
    return {"ok": True}

