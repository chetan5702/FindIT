import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import Principal, get_current_user, require_csrf
from app.errors import APIError
from app.models import Notification, User
from app.schemas import NotificationOut, Page, UnreadCount
from app.services.common import page_count


router = APIRouter(prefix="/notifications", tags=["notifications"])


def notification_out(item: Notification) -> NotificationOut:
    return NotificationOut(
        id=item.id,
        kind=item.kind,
        title=item.title,
        body=item.body,
        message=item.body,
        link=item.link,
        action_url=item.link,
        read_at=item.read_at,
        created_at=item.created_at,
    )


@router.get("", response_model=Page[NotificationOut])
def list_notifications(
    unread_only: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[NotificationOut]:
    filters = [Notification.user_id == user.id]
    if unread_only:
        filters.append(Notification.read_at.is_(None))
    total = db.scalar(select(func.count(Notification.id)).where(*filters)) or 0
    items = list(
        db.scalars(
            select(Notification)
            .where(*filters)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return Page(
        items=[notification_out(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=page_count(total, page_size),
    )


@router.get("/unread-count", response_model=UnreadCount)
def unread_count(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UnreadCount:
    count = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id, Notification.read_at.is_(None)
        )
    ) or 0
    return UnreadCount(unread=count)


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(
    notification_id: uuid.UUID,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> Response:
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == principal.user.id
        )
    )
    if notification is None:
        raise APIError(404, "notification_not_found", "Notification not found")
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(
    principal: Principal = Depends(require_csrf), db: Session = Depends(get_db)
) -> Response:
    db.execute(
        update(Notification)
        .where(Notification.user_id == principal.user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

