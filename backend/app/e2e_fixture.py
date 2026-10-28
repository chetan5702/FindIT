"""Prepare ONLY a disposable development/test database for browser workflow tests."""

import os
from sqlalchemy import select
from app.config import get_settings
from app.database import SessionLocal
from app.models import Category, User
from app.security import hash_password


def main():
    if get_settings().environment not in {"test", "development"}:
        raise SystemExit("E2E fixtures are forbidden outside development/test")
    email = os.environ["FINDIT_E2E_STAFF_EMAIL"]
    password = os.environ["FINDIT_E2E_STAFF_PASSWORD"]
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.email == email)):
            raise SystemExit("Use a fresh E2E database; fixture account already exists")
        db.add(
            User(
                email=email,
                full_name="E2E Staff",
                role="staff",
                email_verified=True,
                password_hash=hash_password(password),
            )
        )
        if not db.scalar(select(Category.id)):
            db.add(Category(name="Electronics", slug="electronics"))
        db.commit()


if __name__ == "__main__":
    main()
