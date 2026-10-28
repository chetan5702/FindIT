from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import APIError
from app.models import AuthSession, User


SESSION_COOKIE = "findit_session"
CSRF_COOKIE = "findit_csrf"
CSRF_HEADER = "X-CSRF-Token"

password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
DUMMY_PASSWORD_HASH = password_hasher.hash("not-a-real-password-123")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return password_hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def digest_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, csrf_token: str, settings: Settings) -> None:
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=settings.session_ttl_hours * 3600,
        secure=settings.cookie_secure,
        httponly=False,
        samesite="lax",
        path="/",
    )


def create_auth_session(
    db: Session,
    user: User,
    response: Response,
    request: Request,
    settings: Settings,
) -> AuthSession:
    session_token = new_token()
    csrf_token = new_token()
    expires_at = datetime.now(UTC) + timedelta(hours=settings.session_ttl_hours)
    auth_session = AuthSession(
        user_id=user.id,
        token_hash=digest_token(session_token),
        csrf_hash=digest_token(csrf_token),
        expires_at=expires_at,
        ip_address=request.client.host if request.client else None,
        user_agent=(request.headers.get("user-agent") or "")[:300] or None,
    )
    db.add(auth_session)
    db.flush()
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        max_age=settings.session_ttl_hours * 3600,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
        path="/",
    )
    set_csrf_cookie(response, csrf_token, settings)
    return auth_session


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE, secure=settings.cookie_secure, httponly=True, samesite="lax", path="/"
    )
    response.delete_cookie(
        CSRF_COOKIE, secure=settings.cookie_secure, httponly=False, samesite="lax", path="/"
    )


def find_auth_session(db: Session, token: str | None) -> AuthSession | None:
    if not token:
        return None
    auth_session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == digest_token(token))
    )
    if auth_session is None:
        return None
    expires_at = auth_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        db.delete(auth_session)
        db.commit()
        return None
    return auth_session


def purge_expired_sessions(db: Session) -> int:
    result = db.execute(delete(AuthSession).where(AuthSession.expires_at <= datetime.now(UTC)))
    return int(result.rowcount or 0)


def verify_double_submit_csrf(request: Request) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE)
    header_token = request.headers.get(CSRF_HEADER)
    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        raise APIError(403, "csrf_failed", "CSRF token is missing or invalid")

