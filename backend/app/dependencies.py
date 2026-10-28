from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import Settings, get_settings
from app.errors import APIError
from app.models import AuthSession, Role, User
from app.security import (
    CSRF_COOKIE,
    CSRF_HEADER,
    digest_token,
    find_auth_session,
    verify_double_submit_csrf,
)


@dataclass
class Principal:
    user: User
    session: AuthSession


def get_optional_principal(
    request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> Principal | None:
    auth_session = find_auth_session(db, request.cookies.get("findit_session"))
    if auth_session is None:
        return None
    user = db.get(User, auth_session.user_id)
    if (
        user is None
        or not user.is_active
        or (settings.require_email_verification and not user.email_verified)
    ):
        return None
    return Principal(user=user, session=auth_session)


def get_principal(principal: Principal | None = Depends(get_optional_principal)) -> Principal:
    if principal is None:
        raise APIError(401, "authentication_required", "Authentication is required")
    return principal


def get_current_user(principal: Principal = Depends(get_principal)) -> User:
    return principal.user


def require_csrf(request: Request, principal: Principal = Depends(get_principal)) -> Principal:
    verify_double_submit_csrf(request)
    csrf = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get(CSRF_HEADER)
    if csrf is None or header is None or digest_token(csrf) != principal.session.csrf_hash:
        raise APIError(403, "csrf_failed", "CSRF token is missing or invalid")
    return principal


def require_public_csrf(request: Request) -> None:
    verify_double_submit_csrf(request)


def require_staff(principal: Principal = Depends(get_principal)) -> User:
    if principal.user.role not in {Role.STAFF.value, Role.ADMIN.value}:
        raise APIError(403, "forbidden", "Campus staff access is required")
    return principal.user


def require_staff_csrf(
    principal: Principal = Depends(require_csrf),
) -> User:
    if principal.user.role not in {Role.STAFF.value, Role.ADMIN.value}:
        raise APIError(403, "forbidden", "Campus staff access is required")
    return principal.user


def require_admin(principal: Principal = Depends(get_principal)) -> User:
    if principal.user.role != Role.ADMIN.value:
        raise APIError(403, "forbidden", "Administrator access is required")
    return principal.user


def require_admin_csrf(principal: Principal = Depends(require_csrf)) -> User:
    if principal.user.role != Role.ADMIN.value:
        raise APIError(403, "forbidden", "Administrator access is required")
    return principal.user
