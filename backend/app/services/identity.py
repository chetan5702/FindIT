from datetime import UTC, datetime, timedelta
from urllib.parse import quote
from sqlalchemy import delete, select
from app.errors import APIError
from app.models import AuthActionToken, User
from app.security import digest_token, new_token
from app.services.mail import deliver

GENERIC_MESSAGE = "If the account is eligible, an email will arrive with the next steps."


def eligible_domain(email, settings):
    return (
        not settings.allowed_email_domains
        or email.rsplit("@", 1)[-1].lower() in settings.allowed_email_domains
    )


def issue(db, user, purpose, settings, tasks):
    # Callers lock the user first; one outstanding token per user and purpose.
    db.execute(
        delete(AuthActionToken).where(
            AuthActionToken.user_id == user.id, AuthActionToken.purpose == purpose
        )
    )
    token = new_token()
    ttl = settings.verification_ttl_minutes if purpose == "verify" else settings.reset_ttl_minutes
    db.add(
        AuthActionToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=digest_token(token),
            expires_at=datetime.now(UTC) + timedelta(minutes=ttl),
        )
    )
    route = "verify-email" if purpose == "verify" else "reset-password"
    link = f"{settings.public_base_url.rstrip('/')}/{route}#token={quote(token)}"
    title = "Verify your FindIt email" if purpose == "verify" else "Reset your FindIt password"
    tasks.add_task(
        deliver,
        settings,
        user.email,
        title,
        f"{title}:\n\n{link}\n\nThis single-use link expires in {ttl} minutes. If you did not request it, ignore this email.",
    )


def consume(db, token, purpose):
    token_hash = digest_token(token)
    # Look up identity first, then always lock user before token (same order as issuance).
    user_id = db.scalar(
        select(AuthActionToken.user_id).where(
            AuthActionToken.token_hash == token_hash, AuthActionToken.purpose == purpose
        )
    )
    user = (
        db.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if user_id
        else None
    )
    action = (
        db.scalar(
            select(AuthActionToken)
            .where(AuthActionToken.token_hash == token_hash, AuthActionToken.purpose == purpose)
            .with_for_update()
        )
        if user
        else None
    )
    expires = action.expires_at if action else None
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if user is None or not user.is_active or action is None or expires <= datetime.now(UTC):
        raise APIError(400, "invalid_token", "This link is invalid or expired. Request a new link.")
    db.delete(action)
    return user
