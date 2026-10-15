"""Session, CSRF bootstrap, registration, login and logout."""
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from ..common import actor_key, mutation, user_json
from ..db import Session, User, db_session
from ..ratelimit import auth_limit
from ..schemas import Credentials, Registration
from ..security import (
    current_session,
    current_user,
    hasher,
    start_session,
    token_hash,
    verify_password,
)
from ..settings import settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/csrf")
def get_csrf(request: Request, response: Response, db=Depends(db_session)):
    actor_key(request, current_user(request, db), response)
    session = current_session(request, db)
    value = request.cookies.get("atlas_csrf") or request.headers.get("x-csrf-token")
    if not value or (session and not secrets.compare_digest(session.csrf_hash, token_hash(value))):
        value = secrets.token_urlsafe(32)
        if session:
            session.csrf_hash = token_hash(value)
            db.commit()
    samesite = "none" if settings.cookie_secure else "lax"
    response.set_cookie("atlas_csrf", value, secure=settings.cookie_secure, samesite=samesite,
                        max_age=7 * 86400, path="/")
    return {"csrf_token": value}


@router.post("/register", dependencies=[Depends(mutation)])
def register(body: Registration, request: Request, response: Response, db=Depends(db_session)):
    auth_limit(request)
    email = body.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    user = User(id=str(uuid.uuid4()), email=email, name=body.name.strip(),
                password_hash=hasher.hash(body.password), admin=False, preferences=[])
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        if db.scalar(select(User).where(User.email == email)):
            raise HTTPException(409, "Email already registered") from None
        raise
    csrf_token = start_session(user, request, response, db)
    return {
        "user": user_json(user),
        "csrf_token": csrf_token,
        "session_token": response.headers.get("x-session-token"),
    }


@router.post("/login", dependencies=[Depends(mutation)])
def login(body: Credentials, request: Request, response: Response, db=Depends(db_session)):
    auth_limit(request)
    user = db.scalar(select(User).where(User.email == body.email.lower().strip()))
    if not user or not verify_password(user.password_hash, body.password):
        raise HTTPException(401, "Invalid email or password")
    csrf_token = start_session(user, request, response, db)
    return {
        "user": user_json(user),
        "csrf_token": csrf_token,
        "session_token": response.headers.get("x-session-token"),
    }


@router.post("/logout", dependencies=[Depends(mutation)])
def logout(request: Request, response: Response, db=Depends(db_session)):
    token = request.cookies.get("atlas_session") or request.headers.get("x-session-token")
    if token:
        db.execute(delete(Session).where(Session.token_hash == token_hash(token)))
    db.commit()
    response.delete_cookie("atlas_session", path="/")
    response.delete_cookie("atlas_csrf", path="/")
    return {"ok": True}
