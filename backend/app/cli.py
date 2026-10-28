from __future__ import annotations

import argparse
import getpass
import os
import sys

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Role, User
from app.security import hash_password
from app.services.common import audit


def create_admin(args: argparse.Namespace) -> int:
    email_value = args.email or input("Administrator email: ").strip()
    try:
        email = validate_email(email_value, check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        print(f"Invalid email: {exc}", file=sys.stderr)
        return 2
    name = " ".join((args.name or input("Administrator full name: ")).split())
    password = os.environ.get("FINDIT_ADMIN_PASSWORD") or getpass.getpass(
        "Administrator password (12+ characters, letter and number): "
    )
    if not 12 <= len(password) <= 128 or not any(c.isalpha() for c in password) or not any(
        c.isdigit() for c in password
    ):
        print("Password must be at least 12 characters and contain a letter and a number.", file=sys.stderr)
        return 2
    if len(name) < 2 or len(name) > 120:
        print("Full name must be between 2 and 120 characters.", file=sys.stderr)
        return 2
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            if existing.role == Role.ADMIN.value and existing.is_active:
                print(f"Active administrator already exists: {email}")
                if not existing.email_verified:
                    print("This pre-upgrade account requires email verification or console verify-admin before sign-in.")
                return 0
            print("A non-administrator account already uses that email.", file=sys.stderr)
            return 1
        user = User(
            email=email,
            full_name=" ".join(name.split()),
            password_hash=hash_password(password),
            role=Role.ADMIN.value,
            email_verified=True,
        )
        db.add(user)
        db.flush()
        audit(db, "admin.created_via_cli", "user", user.id, actor=user)
        db.commit()
        print(f"Created administrator: {email}")
    return 0



def purge_auth(args):
    from datetime import UTC, datetime
    from sqlalchemy import delete
    from app.models import AuthActionToken, AuthRateBucket, AuthSession
    from app.config import get_settings
    import time
    now = datetime.now(UTC)
    with SessionLocal() as db:
        db.execute(delete(AuthActionToken).where(AuthActionToken.expires_at <= now))
        db.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
        db.execute(delete(AuthRateBucket).where(AuthRateBucket.window_start < int(time.time()) - 2 * get_settings().login_attempt_window_seconds))
        db.commit()
    print("Expired authentication records purged")
    return 0


def verify_admin(args):
    from app.security import verify_password
    email = args.email.strip().lower()
    password = getpass.getpass("Current administrator password: ")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email).with_for_update())
        if user is None or not user.is_active or user.role != Role.ADMIN.value or not verify_password(password, user.password_hash):
            print("Administrator identity could not be verified", file=sys.stderr)
            return 1
        user.email_verified = True
        audit(db, "admin.verified_via_console", "user", user.id, actor=user)
        db.commit()
    print("Administrator verified through trusted deployment-console access")
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FindIt Next administrative commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    command = subparsers.add_parser("create-admin", help="Create the initial administrator")
    command.add_argument("--email")
    command.add_argument("--name")
    command.set_defaults(handler=create_admin)
    trusted_admin = subparsers.add_parser("verify-admin", help="Recover verification for a pre-upgrade administrator through trusted console access")
    trusted_admin.add_argument("--email", required=True)
    trusted_admin.set_defaults(handler=verify_admin)
    from app.deployment import check_deployment
    preflight = subparsers.add_parser("check-deployment", help="Validate deployed schema, media and SMTP without sending mail")
    preflight.set_defaults(handler=check_deployment)
    maintenance = subparsers.add_parser("purge-auth", help="Delete expired sessions and one-use tokens")
    maintenance.set_defaults(handler=purge_auth)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())

