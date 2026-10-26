from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Callable

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from database import AuditLog, User, UserSession, get_db, utcnow

SESSION_COOKIE = "ranch_session"
SESSION_HOURS = int(os.getenv("SESSION_HOURS", "12"))
REMEMBER_DAYS = int(os.getenv("REMEMBER_DAYS", "30"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
ALLOWED_ROLES = {"admin", "manager", "veterinary", "staff", "finance", "viewer"}
PH = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)

auth_router = APIRouter(prefix="/api/auth", tags=["authentication"])
user_router = APIRouter(prefix="/api/users", tags=["users"])


class SetupIn(BaseModel):
    bootstrap_token: str | None = None
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)


class UserCreateIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    role: str = "staff"


class UserUpdateIn(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    new_password: str | None = Field(default=None, min_length=10, max_length=128)


def user_public(user: User) -> dict:
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def audit(db: Session, user_id: int | None, action: str, entity_type: str, entity_id: str | int | None = None, description: str | None = None) -> None:
    db.add(AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        description=description,
    ))


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def create_session(db: Session, user: User, remember_me: bool, request: Request) -> tuple[str, datetime]:
    raw = secrets.token_urlsafe(48)
    expires = utcnow() + (timedelta(days=REMEMBER_DAYS) if remember_me else timedelta(hours=SESSION_HOURS))
    db.add(UserSession(
        token_hash=hash_token(raw),
        user_id=user.id,
        expires_at=expires,
        user_agent=(request.headers.get("user-agent") or "")[:500],
    ))
    return raw, expires


def clear_expired_sessions(db: Session) -> None:
    db.query(UserSession).filter(UserSession.expires_at < utcnow()).delete(synchronize_session=False)


def get_current_user(
    ranch_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    if not ranch_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    clear_expired_sessions(db)
    session = db.query(UserSession).filter(UserSession.token_hash == hash_token(ranch_session)).first()
    if not session or aware_utc(session.expires_at) < utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Please sign in again.")
    user = db.query(User).filter(User.id == session.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is inactive.")
    return user


def require_roles(*roles: str) -> Callable:
    allowed = set(roles)

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission for this action.")
        return user

    return dependency


@auth_router.get("/status")
def auth_status(db: Session = Depends(get_db)):
    configured = db.query(User.id).first() is not None
    return {"configured": configured}


@auth_router.post("/setup")
def initial_setup(payload: SetupIn, request: Request, response: Response, db: Session = Depends(get_db)):
    import hmac
    bootstrap_secret=os.getenv('CAPE_BOOTSTRAP_TOKEN','').strip()
    is_production=os.getenv('APP_ENV','development').lower()=='production'
    if (is_production or bootstrap_secret) and (not bootstrap_secret or not hmac.compare_digest((payload.bootstrap_token or '').strip(),bootstrap_secret)):
        raise HTTPException(status_code=403,detail='Valid platform bootstrap token required')
    if db.query(User.id).first() is not None:
        raise HTTPException(status_code=409, detail="Initial administrator has already been created.")
    user = User(
        full_name=payload.full_name.strip(),
        email=str(payload.email).lower(),
        password_hash=PH.hash(payload.password),
        role="platform_owner",
        is_active=True,
    )
    db.add(user)
    db.flush()
    token, expires = create_session(db, user, True, request)
    audit(db, user.id, "setup", "user", user.id, "Created the first administrator account.")
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        expires=expires,
        path="/",
    )
    return {"user": user_public(user)}


@auth_router.post("/login")
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    user = db.query(User).filter(User.email == email).first()
    now = utcnow()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if user.locked_until and aware_utc(user.locked_until) > now:
        raise HTTPException(status_code=423, detail="Account temporarily locked after repeated failed sign-in attempts.")
    try:
        PH.verify(user.password_hash, payload.password)
    except VerifyMismatchError:
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= 5:
            user.locked_until = now + timedelta(minutes=15)
            user.failed_login_attempts = 0
        audit(db, user.id, "login_failed", "user", user.id, "Failed sign-in attempt.")
        db.commit()
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if PH.check_needs_rehash(user.password_hash):
        user.password_hash = PH.hash(payload.password)
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = now
    token, expires = create_session(db, user, payload.remember_me, request)
    audit(db, user.id, "login", "user", user.id, "Signed in.")
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        expires=expires,
        path="/",
    )
    return {"user": user_public(user)}


@auth_router.post("/logout")
def logout(response: Response, ranch_session: str | None = Cookie(default=None, alias=SESSION_COOKIE), db: Session = Depends(get_db)):
    if ranch_session:
        session = db.query(UserSession).filter(UserSession.token_hash == hash_token(ranch_session)).first()
        if session:
            audit(db, session.user_id, "logout", "user", session.user_id, "Signed out.")
            db.delete(session)
            db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@auth_router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user": user_public(user)}


@auth_router.post("/change-password")
def change_password(payload: ChangePasswordIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        PH.verify(user.password_hash, payload.current_password)
    except VerifyMismatchError:
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    user.password_hash = PH.hash(payload.new_password)
    audit(db, user.id, "password_changed", "user", user.id, "Changed account password.")
    db.commit()
    return {"ok": True}


@user_router.get("")
def list_users(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    return {"items": [user_public(x) for x in db.query(User).order_by(User.full_name).all()]}


@user_router.post("")
def create_user(payload: UserCreateIn, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    role = payload.role.lower().strip()
    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {', '.join(sorted(ALLOWED_ROLES))}.")
    email = str(payload.email).lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="A user with this email already exists.")
    item = User(full_name=payload.full_name.strip(), email=email, password_hash=PH.hash(payload.password), role=role)
    db.add(item)
    db.flush()
    audit(db, admin.id, "create", "user", item.id, f"Created user {item.email} with role {role}.")
    db.commit()
    db.refresh(item)
    return {"item": user_public(item)}


@user_router.put("/{user_id}")
def update_user(user_id: int, payload: UserUpdateIn, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    item = db.query(User).filter(User.id == user_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="User not found.")
    if payload.role is not None:
        role = payload.role.lower().strip()
        if role not in ALLOWED_ROLES:
            raise HTTPException(status_code=400, detail="Invalid role.")
        item.role = role
    if payload.full_name is not None:
        item.full_name = payload.full_name.strip()
    if payload.is_active is not None:
        if item.id == admin.id and payload.is_active is False:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account.")
        item.is_active = payload.is_active
    if payload.new_password:
        item.password_hash = PH.hash(payload.new_password)
    audit(db, admin.id, "update", "user", item.id, f"Updated user {item.email}.")
    db.commit()
    db.refresh(item)
    return {"item": user_public(item)}
