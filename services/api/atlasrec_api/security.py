import hashlib
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import HTTPException, Request, Response
from sqlalchemy import delete

from .db import Session, User, now
from .settings import settings

hasher = PasswordHasher()


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def current_session(request: Request, db):
    token = request.cookies.get("atlas_session") or request.headers.get("x-session-token")
    session = db.get(Session, token_hash(token)) if token else None
    if session:
        expiry = session.expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=now().tzinfo)
        if expiry > now():
            return session
    return None


def current_user(request: Request, db, required=False):
    session = current_session(request, db)
    user = db.get(User, session.user_id) if session else None
    if user:
        return user
    if required:
        raise HTTPException(401, "Sign in to continue")
    return None


def require_admin(request, db):
    user = current_user(request, db, True)
    if not user.admin:
        raise HTTPException(403, "Administrator access required")
    return user


def _origin_allowed(origin: str | None, request: Request | None = None) -> bool:
    if not origin:
        return False
    allowed = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
    if origin in allowed:
        return True
    if origin.startswith("https://") and origin.endswith(
        (".hf.space", ".huggingface.co", ".onrender.com", ".vercel.app")
    ):
        return True
    if request is not None:
        fwd_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        if fwd_host and origin in (f"https://{fwd_host}", f"http://{fwd_host}"):
            return True
    return False


def csrf(request, db):
    if not _origin_allowed(request.headers.get("origin"), request):
        raise HTTPException(403, "Origin is not allowed")
    token = request.headers.get("x-csrf-token", "")
    if not token or len(token) < 16:
        raise HTTPException(403, "Invalid CSRF token")
    cookie_csrf = request.cookies.get("atlas_csrf", "")
    if cookie_csrf and not secrets.compare_digest(token, cookie_csrf):
        raise HTTPException(403, "Invalid CSRF token")
    session = current_session(request, db)
    if session and not secrets.compare_digest(session.csrf_hash, token_hash(token)):
        raise HTTPException(403, "Session CSRF token mismatch")


def start_session(user, request, response: Response, db):
    previous = request.cookies.get("atlas_session") or request.headers.get("x-session-token")
    if previous:
        db.execute(delete(Session).where(Session.token_hash == token_hash(previous)))
    token, protection = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.add(Session(token_hash=token_hash(token), user_id=user.id,
                   csrf_hash=token_hash(protection), expires_at=now() + timedelta(days=7)))
    db.commit()
    samesite = "none" if settings.cookie_secure else "lax"
    response.set_cookie("atlas_session", token, httponly=True, secure=settings.cookie_secure,
                        samesite=samesite, max_age=7 * 86400, path="/")
    response.set_cookie("atlas_csrf", protection, secure=settings.cookie_secure,
                        samesite=samesite, max_age=7 * 86400, path="/")
    response.headers["x-session-token"] = token
    return protection


def verify_password(encoded, password):
    try:
        return hasher.verify(encoded, password)
    except VerificationError:
        return False
