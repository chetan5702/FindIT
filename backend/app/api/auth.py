from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status
from datetime import UTC, datetime
import uuid
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.dependencies import (
    Principal,
    get_principal,
    get_current_user,
    get_optional_principal,
    require_csrf,
    require_public_csrf,
)
from app.errors import APIError
from app.models import AuthActionToken, AuthSession, Role, User
from app.schemas import (
    AuthResponse,
    EmailActionRequest,
    PasswordResetRequest,
    PasswordChangeRequest,
    LoginRequest,
    ProfileUpdate,
    RegisterRequest,
    UserOut,
)
from app.security import (
    CSRF_COOKIE,
    digest_token,
    DUMMY_PASSWORD_HASH,
    clear_auth_cookies,
    create_auth_session,
    hash_password,
    needs_rehash,
    new_token,
    set_csrf_cookie,
    verify_password,
)
from app.services.common import audit
from app.services.rate_limits import admit
from app.services.identity import GENERIC_MESSAGE, eligible_domain, issue, consume


router = APIRouter(prefix="/auth", tags=["authentication"])
profile_router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/csrf")
def csrf_token(
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    principal: Principal | None = Depends(get_optional_principal),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    token = request.cookies.get(CSRF_COOKIE)
    if principal is not None:
        auth_session = db.scalar(
            select(AuthSession)
            .where(AuthSession.id == principal.session.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if auth_session is None:
            token = new_token()
        elif not token or digest_token(token) != auth_session.csrf_hash:
            token = new_token()
            auth_session.csrf_hash = digest_token(token)
            db.commit()
    elif not token:
        token = new_token()
    set_csrf_cookie(response, token, settings)
    response.headers["Cache-Control"] = "no-store"
    return {"csrf_token": token}


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_public_csrf)],
)
def register(
    payload: RegisterRequest,
    tasks: BackgroundTasks,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    client_ip = request.client.host if request.client else "unknown"
    admit(
        db,
        [(f"register:ip:{client_ip}", settings.registration_attempt_limit)],
        settings.login_attempt_window_seconds,
    )
    if not eligible_domain(payload.email, settings):
        raise APIError(
            422,
            "institutional_email_required",
            "Use an email from your institution's approved domain",
        )
    # Do comparable password work for existing and new identities.
    password_hash = hash_password(payload.password)
    existing = db.scalar(select(User).where(User.email == payload.email).with_for_update())
    if existing:
        if settings.require_email_verification:
            if existing.is_active and not existing.email_verified:
                issue(db, existing, "verify", settings, tasks)
                db.commit()
            return AuthResponse(verification_required=True, message=GENERIC_MESSAGE)
        raise APIError(409, "email_in_use", "An account with this email already exists")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=password_hash,
        role=Role.STUDENT.value,
    )
    db.add(user)
    try:
        db.flush()
        if settings.require_email_verification:
            issue(db, user, "verify", settings, tasks)
        else:
            create_auth_session(db, user, response, request, settings)
        audit(
            db,
            "auth.registered",
            "user",
            user.id,
            actor=user,
            ip_address=request.client.host if request.client else None,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        if settings.require_email_verification:
            return AuthResponse(verification_required=True, message=GENERIC_MESSAGE)
        raise APIError(409, "email_in_use", "An account with this email already exists") from None
    if settings.require_email_verification:
        return AuthResponse(verification_required=True, message=GENERIC_MESSAGE)
    return AuthResponse(user=UserOut.model_validate(user))


@router.post("/login", response_model=AuthResponse, dependencies=[Depends(require_public_csrf)])
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthResponse:
    client_ip = request.client.host if request.client else "unknown"
    admit(
        db,
        [
            (f"login:ip:{client_ip}", settings.login_ip_attempt_limit),
            (f"login:account:{payload.email}", settings.login_attempt_limit),
        ],
        settings.login_attempt_window_seconds,
    )
    user = db.scalar(select(User).where(User.email == payload.email).with_for_update())
    valid = verify_password(payload.password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if user is None or not valid or not user.is_active:
        raise APIError(401, "invalid_credentials", "Email or password is incorrect")
    if settings.require_email_verification and not user.email_verified:
        raise APIError(
            403, "email_verification_required", "Verify your institutional email before signing in"
        )
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    from app.security import SESSION_COOKIE, digest_token

    old = request.cookies.get(SESSION_COOKIE)
    if old:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == digest_token(old)))
    create_auth_session(db, user, response, request, settings)
    audit(db, "auth.logged_in", "user", user.id, actor=user, ip_address=client_ip)
    db.commit()
    return AuthResponse(user=UserOut.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    request: Request,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    db.delete(principal.session)
    audit(
        db,
        "auth.logged_out",
        "user",
        principal.user.id,
        actor=principal.user,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    clear_auth_cookies(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@profile_router.get("", response_model=UserOut)
def get_profile(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@profile_router.patch("", response_model=UserOut)
def update_profile(
    payload: ProfileUpdate,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> UserOut:
    principal.user.full_name = payload.full_name
    audit(db, "profile.updated", "user", principal.user.id, actor=principal.user)
    db.commit()
    return UserOut.model_validate(principal.user)


@router.post("/verification/request", dependencies=[Depends(require_public_csrf)])
def request_verification(
    payload: EmailActionRequest,
    tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    request_identity_link(payload.email, "verify", tasks, request, db, settings)
    return {"message": GENERIC_MESSAGE}


@router.post("/password/forgot", dependencies=[Depends(require_public_csrf)])
def forgot_password(
    payload: EmailActionRequest,
    tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    request_identity_link(payload.email, "reset", tasks, request, db, settings)
    return {"message": GENERIC_MESSAGE}


def request_identity_link(email, purpose, tasks, request, db, settings):
    ip = request.client.host if request.client else "unknown"
    admit(
        db,
        [
            (f"identity:ip:{ip}", settings.identity_ip_request_limit),
            (f"identity:{email}", settings.identity_request_limit),
        ],
        settings.login_attempt_window_seconds,
    )
    user = db.scalar(select(User).where(User.email == email).with_for_update())
    if user and user.is_active and (purpose == "reset" or eligible_domain(email, settings)):
        if (purpose == "verify" and not user.email_verified) or (
            purpose == "reset" and user.email_verified
        ):
            issue(db, user, purpose, settings, tasks)
            audit(db, f"auth.{purpose}_requested", "user", user.id, actor=user)
            db.commit()


@router.post("/verification/confirm", dependencies=[Depends(require_public_csrf)])
def confirm_verification(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    ip = request.client.host if request.client else "unknown"
    admit(
        db,
        [(f"token:ip:{ip}", settings.identity_ip_request_limit)],
        settings.login_attempt_window_seconds,
    )
    user = consume(db, payload.token, "verify")
    if not eligible_domain(user.email, settings):
        raise APIError(400, "invalid_token", "This institutional email is no longer eligible")
    # Set a mailbox-owner chosen password to prevent pre-registration takeover.
    user.password_hash = hash_password(payload.password)
    user.email_verified = True
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    audit(db, "auth.email_verified", "user", user.id, actor=user)
    db.commit()
    return {"message": "Email verified. You can now sign in."}


@router.post("/password/reset", dependencies=[Depends(require_public_csrf)])
def reset_password(
    payload: PasswordResetRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    ip = request.client.host if request.client else "unknown"
    admit(
        db,
        [(f"token:ip:{ip}", settings.identity_ip_request_limit)],
        settings.login_attempt_window_seconds,
    )
    password_hash = hash_password(payload.password)
    user = consume(db, payload.token, "reset")
    user.password_hash = password_hash
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.execute(delete(AuthActionToken).where(AuthActionToken.user_id == user.id))
    audit(db, "auth.password_reset", "user", user.id, actor=user)
    db.commit()
    clear_auth_cookies(response, settings)
    return {"message": "Password reset. Sign in again on each device."}


@router.post("/password/change")
def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    response: Response,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    ip = request.client.host if request.client else "unknown"
    admit(
        db,
        [
            (f"password:ip:{ip}", settings.identity_ip_request_limit),
            (f"password:user:{principal.user.id}", settings.identity_request_limit),
        ],
        settings.login_attempt_window_seconds,
    )
    user = db.scalar(
        select(User)
        .where(User.id == principal.user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not user.is_active or not verify_password(payload.current_password, user.password_hash):
        raise APIError(401, "invalid_credentials", "Current password is incorrect")
    user.password_hash = hash_password(payload.password)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.execute(delete(AuthActionToken).where(AuthActionToken.user_id == user.id))
    audit(db, "auth.password_changed", "user", user.id, actor=user)
    db.commit()
    clear_auth_cookies(response, settings)
    return {"message": "Password changed. Sign in again on each device."}


@router.get("/sessions")
def list_sessions(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    sessions = db.scalars(
        select(AuthSession)
        .where(AuthSession.user_id == principal.user.id, AuthSession.expires_at > datetime.now(UTC))
        .order_by(AuthSession.created_at.desc())
    )
    return [
        {
            "id": item.id,
            "created_at": item.created_at,
            "expires_at": item.expires_at,
            "user_agent": item.user_agent,
            "current": item.id == principal.session.id,
        }
        for item in sessions
    ]


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(
    session_id: uuid.UUID,
    response: Response,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    item = db.scalar(
        select(AuthSession).where(
            AuthSession.id == session_id, AuthSession.user_id == principal.user.id
        )
    )
    if item is None:
        raise APIError(404, "session_not_found", "Session not found")
    db.delete(item)
    audit(db, "auth.session_revoked", "user", principal.user.id, actor=principal.user)
    db.commit()
    if session_id == principal.session.id:
        clear_auth_cookies(response, settings)
    response.status_code = 204
    return response


@router.post("/logout-all", status_code=204)
def logout_all(
    response: Response,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    db.execute(delete(AuthSession).where(AuthSession.user_id == principal.user.id))
    audit(db, "auth.all_sessions_revoked", "user", principal.user.id, actor=principal.user)
    db.commit()
    clear_auth_cookies(response, settings)
    response.status_code = 204
    return response
