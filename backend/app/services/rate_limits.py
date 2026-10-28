"""Shared atomic authentication admission limits; keys never store raw identities."""

import hashlib
import time

from sqlalchemy import delete, case, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.errors import APIError
from app.models import AuthRateBucket


def admit(db: Session, limits: list[tuple[str, int]], window_seconds: int) -> None:
    now = int(time.time())
    start = now - now % window_seconds
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    # Purge separately and skip active admissions to avoid lock-order conflicts.
    expired = list(
        db.scalars(
            select(AuthRateBucket.key)
            .where(AuthRateBucket.window_start < start - window_seconds)
            .order_by(AuthRateBucket.key)
            .limit(1000)
            .with_for_update(skip_locked=True)
        )
    )
    if expired:
        db.execute(delete(AuthRateBucket).where(AuthRateBucket.key.in_(expired)))
    db.commit()
    blocked = False
    # Keep ordering stable when multiple requests share some buckets.
    for identity, limit in sorted(limits):
        key = hashlib.sha256(identity.encode()).hexdigest()
        stmt = insert(AuthRateBucket).values(key=key, window_start=start, attempts=1)
        current = AuthRateBucket.window_start == start
        stmt = stmt.on_conflict_do_update(
            index_elements=[AuthRateBucket.key],
            set_={
                "window_start": start,
                "attempts": case((current, AuthRateBucket.attempts + 1), else_=1),
            },
        ).returning(AuthRateBucket.attempts)
        blocked = db.scalar(stmt) > limit or blocked
    db.commit()
    if blocked:
        raise APIError(
            429,
            "rate_limited",
            "Too many authentication requests. Try again later.",
            headers={"Retry-After": str(start + window_seconds - now)},
        )
