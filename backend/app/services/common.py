import json
import math
import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent, Notification, User


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "item"


def page_count(total: int, page_size: int) -> int:
    return math.ceil(total / page_size) if total else 0


def notify(
    db: Session,
    user_id: uuid.UUID,
    kind: str,
    title: str,
    body: str,
    link: str | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        kind=kind,
        title=title,
        body=body,
        link=link,
    )
    db.add(notification)
    return notification


def audit(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    actor: User | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor.id if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=json.dumps(metadata or {}, separators=(",", ":"), default=str),
        ip_address=ip_address,
    )
    db.add(event)
    return event

