"""Helpers shared by several routers: CSRF dependency, identity and serialization."""
from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, Request
from sqlalchemy import update

from .db import Product, User, db_session
from .security import csrf, token_hash
from .settings import settings


def mutation(request: Request, db=Depends(db_session)):
    """Dependency for every state-changing route: Origin + double-submit CSRF check."""
    csrf(request, db)


def bump_history(db, user):
    # Increment in the database so simultaneous feedback cannot lose cache invalidations.
    db.execute(update(User).where(User.id == user.id).values(
        history_revision=User.history_revision + 1).execution_options(synchronize_session=False))
    db.refresh(user)


def user_json(user):
    created = getattr(user, "created_at", None)
    return {"id": user.id, "email": user.email, "name": user.name, "admin": user.admin,
            "preferences": user.preferences, "history_revision": user.history_revision,
            "created_at": created.isoformat() if created else None}


PRODUCT_FIELDS = ("id", "title", "description", "category", "price", "currency", "image", "available")


def product_json(p):
    return {k: getattr(p, k) for k in PRODUCT_FIELDS}


def lookup_product(db, item):
    p = db.get(Product, item)
    if not p or p.profile != settings.profile:
        raise HTTPException(404, "Product not found")
    return p


def actor_key(request, user, response=None):
    """Stable owner key: the user id, or a hashed guest cookie (issued when a response is given)."""
    if user:
        return "u:" + user.id
    token = request.cookies.get("atlas_guest")
    if not token and response is not None:
        token = secrets.token_urlsafe(32)
        response.set_cookie("atlas_guest", token, httponly=True, secure=settings.cookie_secure,
                            samesite="lax", max_age=86400, path="/")
    return "g:" + token_hash(token) if token else None
