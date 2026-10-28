from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.serializers import audit_out
from app.config import Settings, get_settings
from app.database import get_db
from app.dependencies import require_admin, require_admin_csrf
from app.errors import APIError
from app.models import (
    AuthSession,
    AuthActionToken,
    AuditEvent,
    Category,
    Claim,
    CustodyRecord,
    Handover,
    Location,
    Report,
    Role,
    User,
)
from app.schemas import (
    AdminDashboardOut,
    AdminUserUpdate,
    AuditEventOut,
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    LocationAdminOut,
    LocationCreate,
    LocationUpdate,
    Page,
    ReportStatusUpdate,
    UserOut,
)
from app.services.common import audit, page_count, slugify


router = APIRouter(prefix="/admin", tags=["administration"])


def reporting_url(location: Location, settings: Settings) -> str:
    return (
        f"{settings.public_base_url.rstrip('/')}/app/report/found"
        f"?location={location.id}&source=qr&token={location.qr_token}"
    )


def location_admin_out(location: Location, settings: Settings) -> LocationAdminOut:
    return LocationAdminOut(
        id=location.id,
        name=location.name,
        slug=location.slug,
        description=location.description,
        building=location.building,
        is_active=location.is_active,
        qr_token=location.qr_token,
        reporting_url=reporting_url(location, settings),
    )


@router.get("/dashboard", response_model=AdminDashboardOut)
def admin_dashboard(
    admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> AdminDashboardOut:
    status_rows = db.execute(
        select(Report.status, func.count(Report.id)).group_by(Report.status)
    ).all()
    return AdminDashboardOut(
        users=db.scalar(select(func.count(User.id))) or 0,
        active_reports=db.scalar(
            select(func.count(Report.id)).where(Report.status.notin_(["archived", "returned"]))
        )
        or 0,
        staff=db.scalar(
            select(func.count(User.id)).where(
                User.role.in_([Role.STAFF.value, Role.ADMIN.value]), User.is_active.is_(True)
            )
        )
        or 0,
        returns=db.scalar(select(func.count(Handover.id))) or 0,
        categories=db.scalar(select(func.count(Category.id)).where(Category.is_active.is_(True)))
        or 0,
        locations=db.scalar(select(func.count(Location.id)).where(Location.is_active.is_(True)))
        or 0,
        reports_by_status={name: count for name, count in status_rows},
    )


@router.get("/users", response_model=Page[UserOut])
def list_users(
    q: str | None = Query(default=None, max_length=120),
    role: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Page[UserOut]:
    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(User.email.ilike(pattern), User.full_name.ilike(pattern)))
    if role:
        if role not in {item.value for item in Role}:
            raise APIError(422, "invalid_role", "Unknown user role")
        filters.append(User.role == role)
    total = db.scalar(select(func.count(User.id)).where(*filters)) or 0
    users = list(
        db.scalars(
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc(), User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return Page(
        items=[UserOut.model_validate(user) for user in users],
        total=total,
        page=page,
        page_size=page_size,
        pages=page_count(total, page_size),
    )


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    admin: User = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
) -> UserOut:
    # One transaction-scoped lock serializes every administrator membership change.
    # Acquire it before any user row locks to avoid lock-order inversion.
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(7241032281)"))
    db.refresh(admin)
    if not admin.is_active or admin.role != Role.ADMIN.value:
        raise APIError(403, "forbidden", "Administrator access is required")
    user = db.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None:
        raise APIError(404, "user_not_found", "User not found")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return UserOut.model_validate(user)
    removes_active_admin = (
        user.role == Role.ADMIN.value
        and user.is_active
        and (
            changes.get("role", Role.ADMIN.value) != Role.ADMIN.value
            or changes.get("is_active", True) is False
        )
    )
    if removes_active_admin:
        active_admins = (
            db.scalar(
                select(func.count(User.id)).where(
                    User.role == Role.ADMIN.value, User.is_active.is_(True)
                )
            )
            or 0
        )
        if active_admins <= 1:
            raise APIError(409, "last_admin", "The last active administrator cannot be removed")
    if user.id == admin.id and changes.get("is_active") is False:
        raise APIError(409, "self_deactivation", "You cannot deactivate your own account")
    for key, value in changes.items():
        setattr(user, key, value)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    if not user.is_active:
        db.execute(delete(AuthActionToken).where(AuthActionToken.user_id == user.id))
    audit(
        db,
        "user.permissions_updated",
        "user",
        user.id,
        actor=admin,
        metadata={"fields": sorted(changes), "role": user.role, "is_active": user.is_active},
    )
    db.commit()
    return UserOut.model_validate(user)


@router.get("/audit-events", response_model=Page[AuditEventOut])
def list_audit_events(
    action: str | None = Query(default=None, max_length=100),
    entity_type: str | None = Query(default=None, max_length=50),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Page[AuditEventOut]:
    filters = []
    if action:
        filters.append(AuditEvent.action == action)
    if entity_type:
        filters.append(AuditEvent.entity_type == entity_type)
    total = db.scalar(select(func.count(AuditEvent.id)).where(*filters)) or 0
    events = list(
        db.scalars(
            select(AuditEvent)
            .where(*filters)
            .options(selectinload(AuditEvent.actor))
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return Page(
        items=[audit_out(event) for event in events],
        total=total,
        page=page,
        page_size=page_size,
        pages=page_count(total, page_size),
    )


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate,
    admin: User = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
) -> Category:
    category = Category(
        name=payload.name.strip(),
        slug=slugify(payload.name),
        description=payload.description.strip() if payload.description else None,
    )
    db.add(category)
    try:
        db.flush()
        audit(db, "category.created", "category", category.id, actor=admin)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise APIError(409, "category_exists", "A category with this name already exists") from None
    return category


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    admin: User = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise APIError(404, "category_not_found", "Category not found")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        changes["slug"] = slugify(changes["name"])
    for key, value in changes.items():
        setattr(category, key, value)
    audit(
        db,
        "category.updated",
        "category",
        category.id,
        actor=admin,
        metadata={"fields": sorted(changes)},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise APIError(409, "category_exists", "A category with this name already exists") from None
    return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: uuid.UUID,
    admin: User = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
) -> Response:
    category = db.get(Category, category_id)
    if category is None:
        raise APIError(404, "category_not_found", "Category not found")
    category.is_active = False
    audit(db, "category.deactivated", "category", category.id, actor=admin)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/locations", response_model=LocationAdminOut, status_code=status.HTTP_201_CREATED)
def create_location(
    payload: LocationCreate,
    admin: User = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LocationAdminOut:
    location = Location(
        name=payload.name.strip(),
        slug=slugify(payload.name),
        description=payload.description.strip() if payload.description else None,
        building=payload.building.strip() if payload.building else None,
    )
    db.add(location)
    try:
        db.flush()
        audit(db, "location.created", "location", location.id, actor=admin)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise APIError(409, "location_exists", "A location with this name already exists") from None
    return location_admin_out(location, settings)


@router.patch("/locations/{location_id}", response_model=LocationAdminOut)
def update_location(
    location_id: uuid.UUID,
    payload: LocationUpdate,
    admin: User = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LocationAdminOut:
    location = db.get(Location, location_id)
    if location is None:
        raise APIError(404, "location_not_found", "Location not found")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        changes["slug"] = slugify(changes["name"])
    for key, value in changes.items():
        setattr(location, key, value)
    audit(
        db,
        "location.updated",
        "location",
        location.id,
        actor=admin,
        metadata={"fields": sorted(changes)},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise APIError(409, "location_exists", "A location with this name already exists") from None
    return location_admin_out(location, settings)


@router.delete("/locations/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_location(
    location_id: uuid.UUID,
    admin: User = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
) -> Response:
    location = db.get(Location, location_id)
    if location is None:
        raise APIError(404, "location_not_found", "Location not found")
    location.is_active = False
    audit(db, "location.deactivated", "location", location.id, actor=admin)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/reports/{report_id}/status", status_code=status.HTTP_204_NO_CONTENT)
def moderate_report(
    report_id: uuid.UUID,
    payload: ReportStatusUpdate,
    admin: User = Depends(require_admin_csrf),
    db: Session = Depends(get_db),
) -> Response:
    report = db.scalar(select(Report).where(Report.id == report_id).with_for_update())
    if report is None:
        raise APIError(404, "report_not_found", "Report not found")
    if payload.status == report.status:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    if payload.status not in {"open", "archived"}:
        raise APIError(
            409,
            "workflow_required",
            "Use claim review, custody and handover workflows to change this status",
        )
    if report.status == "returned":
        raise APIError(409, "report_locked", "Completed returns cannot be reopened")
    if report.status == "in_custody" or db.scalar(
        select(CustodyRecord.id).where(CustodyRecord.found_report_id == report.id)
    ):
        raise APIError(409, "custody_exists", "Reports with custody history cannot be moderated")
    if db.scalar(
        select(Claim.id)
        .where(or_(Claim.found_report_id == report.id, Claim.lost_report_id == report.id))
        .limit(1)
    ):
        raise APIError(
            409, "claim_history_exists", "Reports with claim history cannot be moderated"
        )
    previous = report.status
    report.status = payload.status
    audit(
        db,
        "report.moderated",
        "report",
        report.id,
        actor=admin,
        metadata={"from": previous, "to": payload.status, "reason": payload.reason},
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
