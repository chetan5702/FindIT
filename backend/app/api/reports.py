from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.database import get_db
from app.dependencies import Principal, get_current_user, require_csrf
from app.errors import APIError
from app.models import Category, Claim, Location, Report, ReportImage, ReportStatus, User
from app.schemas import MatchOut, MatchReason, Page, ReportCreate, ReportImageOut, ReportOut, ReportSummary, ReportUpdate
from app.storage import EXTENSIONS, LocalStorage, validate_image
from app.services.upload_limits import lock_uploader, check_upload_quota
from app.services.common import audit, notify, page_count
from app.services.matching import rank_candidates, to_matchable
from app.api.serializers import image_out, report_out, report_summary


router = APIRouter(prefix="/reports", tags=["reports"])

REPORT_LOADS = (
    selectinload(Report.category),
    selectinload(Report.location),
    selectinload(Report.images),
    selectinload(Report.reporter),
)


def load_report(db: Session, report_id: uuid.UUID, *, for_update: bool = False) -> Report:
    statement = select(Report).where(Report.id == report_id).options(*REPORT_LOADS)
    if for_update:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    report = db.scalar(statement)
    if report is None:
        raise APIError(404, "report_not_found", "Report not found")
    return report


def validate_catalog(db: Session, category_id: uuid.UUID, location_id: uuid.UUID | None) -> None:
    category = db.get(Category, category_id)
    if category is None or not category.is_active:
        raise APIError(422, "invalid_category", "Select an active category")
    if location_id is not None:
        location = db.get(Location, location_id)
        if location is None or not location.is_active:
            raise APIError(422, "invalid_location", "Select an active campus location")


def can_view_archived(report: Report, user: User) -> bool:
    return report.status != ReportStatus.ARCHIVED.value or user.id == report.reporter_id or user.role in {
        "staff",
        "admin",
    }


@router.get("/public", response_model=Page[ReportSummary])
def public_reports(
    report_type: str | None = Query(default=None, pattern="^(lost|found)$"),
    category_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    q: str | None = Query(default=None, min_length=1, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=50),
    db: Session = Depends(get_db),
) -> Page[ReportSummary]:
    """Small, privacy-minimized anonymous catalog: never expose ownership proof or photo URLs."""
    filters = [Report.status.in_(["open", "matched", "in_custody"])]
    if report_type:
        filters.append(Report.report_type == report_type)
    if category_id:
        filters.append(Report.category_id == category_id)
    if location_id:
        filters.append(Report.location_id == location_id)
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(Report.item_name.ilike(pattern), Report.description.ilike(pattern), Report.public_details.ilike(pattern), Report.approximate_location.ilike(pattern)))
    total = db.scalar(select(func.count(Report.id)).where(*filters)) or 0
    reports = list(db.scalars(
        select(Report).where(*filters).options(*REPORT_LOADS)
        .order_by(Report.occurred_at.desc(), Report.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ))
    summaries = []
    for report in reports:
        # Explicit public projection: photo metadata/URLs and private verification
        # are deliberately NOT accessible through anonymous discovery.
        item = report_summary(report)
        item.images = []
        item.image_count = 0
        item.thumbnail_url = None
        summaries.append(item)
    return Page(items=summaries, total=total, page=page, page_size=page_size, pages=page_count(total, page_size))


@router.get("", response_model=Page)
def list_reports(
    report_type: str | None = Query(default=None, pattern="^(lost|found)$"),
    category_id: uuid.UUID | None = None,
    location_id: uuid.UUID | None = None,
    report_status: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mine: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page:
    filters = []
    if report_type:
        filters.append(Report.report_type == report_type)
    if category_id:
        filters.append(Report.category_id == category_id)
    if location_id:
        filters.append(Report.location_id == location_id)
    if report_status:
        allowed = {"open", "matched", "in_custody", "returned", "archived"}
        if report_status not in allowed:
            raise APIError(422, "invalid_status", "Unknown report status")
        filters.append(Report.status == report_status)
    else:
        filters.append(Report.status != ReportStatus.ARCHIVED.value)
    # Archived records are only visible to their owner or authorized staff.
    # This restriction applies to BOTH the count and data query.
    if user.role not in {"staff", "admin"}:
        filters.append(or_(Report.status != ReportStatus.ARCHIVED.value, Report.reporter_id == user.id))
    if mine:
        filters.append(Report.reporter_id == user.id)
    if date_from:
        filters.append(Report.occurred_at >= date_from)
    if date_to:
        filters.append(Report.occurred_at <= date_to)
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                Report.item_name.ilike(pattern),
                Report.description.ilike(pattern),
                Report.public_details.ilike(pattern),
                Report.approximate_location.ilike(pattern),
            )
        )
    total = db.scalar(select(func.count(Report.id)).where(*filters)) or 0
    reports = list(
        db.scalars(
            select(Report)
            .where(*filters)
            .options(*REPORT_LOADS)
            .order_by(Report.occurred_at.desc(), Report.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return Page(
        items=[report_out(report, user) for report in reports],
        total=total,
        page=page,
        page_size=page_size,
        pages=page_count(total, page_size),
    )


@router.post("", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: ReportCreate,
    request: Request,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> ReportOut:
    validate_catalog(db, payload.category_id, payload.location_id)
    report = Report(reporter_id=principal.user.id, **payload.model_dump())
    db.add(report)
    db.flush()
    audit(
        db,
        "report.created",
        "report",
        report.id,
        actor=principal.user,
        metadata={"report_type": report.report_type},
        ip_address=request.client.host if request.client else None,
    )

    # All eligible reports are scored. Only after ranking do we limit notification noise.
    candidates = list(
        db.scalars(
            select(Report)
            .where(
                Report.report_type != report.report_type,
                Report.reporter_id != report.reporter_id,
                Report.status.in_(["open", "matched", "in_custody"]),
            )
            .options(selectinload(Report.images))
        )
    )
    ranked = rank_candidates(to_matchable(report), (to_matchable(item) for item in candidates), minimum_score=55)
    by_id = {candidate.id: candidate for candidate in candidates}
    for match in ranked[:5]:
        candidate = by_id[match.candidate_id]
        notify(
            db,
            candidate.reporter_id,
            "likely_match",
            "A possible match was reported",
            f"A complementary {report.report_type} report may match your {candidate.item_name}.",
            f"/app/reports/{candidate.id}/matches",
        )
        notify(
            db,
            report.reporter_id,
            "likely_match",
            "We found a possible match",
            f"A {candidate.report_type} report may match your {report.item_name}.",
            f"/app/reports/{report.id}/matches",
        )
    db.commit()
    return report_out(load_report(db, report.id), principal.user)


@router.get("/{report_id}", response_model=ReportOut)
def get_report(
    report_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportOut:
    report = load_report(db, report_id)
    if not can_view_archived(report, user):
        raise APIError(404, "report_not_found", "Report not found")
    return report_out(report, user)


@router.patch("/{report_id}", response_model=ReportOut)
def update_report(
    report_id: uuid.UUID,
    payload: ReportUpdate,
    request: Request,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> ReportOut:
    report = load_report(db, report_id, for_update=True)
    if principal.user.id != report.reporter_id and principal.user.role != "admin":
        raise APIError(403, "forbidden", "Only the report owner can edit this report")
    if report.status in {"returned", "archived"}:
        raise APIError(409, "report_locked", "A returned or archived report cannot be edited")
    changes = payload.model_dump(exclude_unset=True)
    identity_fields = {"item_name", "category_id", "location_id", "occurred_at"}
    has_claim_history = db.scalar(select(Claim.id).where(or_(Claim.found_report_id == report.id, Claim.lost_report_id == report.id)).limit(1))
    if has_claim_history and identity_fields.intersection(changes):
        raise APIError(
            409,
            "identity_locked",
            "Core report identity fields cannot change after a claim has been submitted",
        )
    validate_catalog(
        db,
        changes.get("category_id", report.category_id),
        changes.get("location_id", report.location_id),
    )
    for key, value in changes.items():
        setattr(report, key, value)
    audit(
        db,
        "report.updated",
        "report",
        report.id,
        actor=principal.user,
        metadata={"fields": sorted(changes)},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return report_out(load_report(db, report.id), principal.user)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_report(
    report_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> Response:
    report = load_report(db, report_id, for_update=True)
    if principal.user.id != report.reporter_id and principal.user.role != "admin":
        raise APIError(403, "forbidden", "Only the report owner can archive this report")
    if db.scalar(select(Claim.id).where(or_(Claim.found_report_id == report.id, Claim.lost_report_id == report.id)).limit(1)):
        raise APIError(409, "claim_history_exists", "Reports with claim history cannot be archived")
    from app.models import CustodyRecord
    if report.status in {"returned", "in_custody"} or db.scalar(
        select(CustodyRecord.id).where(CustodyRecord.found_report_id == report.id)
    ):
        raise APIError(409, "report_locked", "Reports with custody history or completed returns cannot be archived")
    report.status = ReportStatus.ARCHIVED.value
    audit(
        db,
        "report.archived",
        "report",
        report.id,
        actor=principal.user,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{report_id}/images",
    response_model=ReportImageOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_report_image(
    report_id: uuid.UUID,
    file: UploadFile = File(...),
    alt_text: str | None = Form(default=None, max_length=250),
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ReportImageOut:
    upload_target = db.get(Report, report_id)
    if upload_target is None:
        raise APIError(404, "report_not_found", "Report not found")
    lock_uploader(db, upload_target.reporter_id)
    report = load_report(db, report_id, for_update=True)
    if principal.user.id != report.reporter_id and principal.user.role != "admin":
        raise APIError(403, "forbidden", "Only the report owner can upload images")
    if report.status in {"returned", "archived"}:
        raise APIError(409, "report_locked", "Images cannot be changed on this report")
    if len(report.images) >= settings.max_report_images:
        raise APIError(409, "image_limit", "The report already has the maximum number of images")
    if db.scalar(select(Claim.id).where(or_(Claim.found_report_id == report.id, Claim.lost_report_id == report.id)).limit(1)):
        raise APIError(409, "claim_history_exists", "Images are locked after a claim is submitted")
    content = await file.read(settings.max_upload_bytes + 1)
    validated = validate_image(content, file.content_type, settings.max_upload_bytes)
    check_upload_quota(db, report.reporter_id, validated.byte_size, settings)
    storage = LocalStorage(settings.media_root)
    storage_key = storage.save(
        f"reports-{report.id}", validated.content, EXTENSIONS[validated.mime_type]
    )
    image = ReportImage(
        report_id=report.id,
        storage_key=storage_key,
        original_name=(file.filename or "image")[:255],
        mime_type=validated.mime_type,
        byte_size=validated.byte_size,
        sha256=validated.sha256,
        alt_text=alt_text,
    )
    db.add(image)
    audit(db, "report.image_added", "report", report.id, actor=principal.user)
    try:
        db.commit()
    except Exception:
        storage.delete(storage_key)
        raise
    db.refresh(image)
    return image_out(image, report.id)


@router.get("/{report_id}/images/{image_id}")
def get_report_image(
    report_id: uuid.UUID,
    image_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    report = load_report(db, report_id)
    if not can_view_archived(report, user):
        raise APIError(404, "image_not_found", "Image not found")
    image = db.scalar(
        select(ReportImage).where(ReportImage.id == image_id, ReportImage.report_id == report_id)
    )
    if image is None:
        raise APIError(404, "image_not_found", "Image not found")
    path = LocalStorage(settings.media_root).path_for(image.storage_key)
    if not path.is_file():
        raise APIError(404, "image_not_found", "Image not found")
    return FileResponse(path, media_type=image.mime_type, headers={"Cache-Control": "private, max-age=3600"})


@router.delete("/{report_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report_image(
    report_id: uuid.UUID,
    image_id: uuid.UUID,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    report = load_report(db, report_id, for_update=True)
    if principal.user.id != report.reporter_id and principal.user.role != "admin":
        raise APIError(403, "forbidden", "Only the report owner can remove images")
    if report.status in {"returned", "archived"} or db.scalar(
        select(Claim.id).where(or_(Claim.found_report_id == report.id, Claim.lost_report_id == report.id)).limit(1)
    ):
        raise APIError(409, "report_locked", "Images are locked for this report")
    image = db.scalar(
        select(ReportImage).where(ReportImage.id == image_id, ReportImage.report_id == report_id)
    )
    if image is None:
        raise APIError(404, "image_not_found", "Image not found")
    storage_key = image.storage_key
    db.delete(image)
    audit(db, "report.image_removed", "report", report.id, actor=principal.user)
    db.commit()
    LocalStorage(settings.media_root).delete(storage_key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{report_id}/matches", response_model=Page[MatchOut])
def report_matches(
    report_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    minimum_score: int = Query(default=1, ge=0, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[MatchOut]:
    source = load_report(db, report_id)
    if user.id != source.reporter_id and user.role not in {"staff", "admin"}:
        raise APIError(403, "forbidden", "Only the report owner or staff can view matches")
    # Deliberately no SQL LIMIT: ranking sees every eligible historical candidate.
    candidates = list(
        db.scalars(
            select(Report)
            .where(
                Report.id != source.id,
                Report.report_type != source.report_type,
                Report.reporter_id != source.reporter_id,
                Report.status.in_(["open", "matched", "in_custody"]),
            )
            .options(*REPORT_LOADS)
        )
    )
    ranked = rank_candidates(
        to_matchable(source),
        (to_matchable(candidate) for candidate in candidates),
        minimum_score=minimum_score,
    )
    total = len(ranked)
    selected = ranked[(page - 1) * page_size : page * page_size]
    by_id = {candidate.id: candidate for candidate in candidates}
    items = [
        MatchOut(
            report=report_summary(by_id[result.candidate_id]),
            score=result.score,
            reasons=[MatchReason(**reason.__dict__) for reason in result.reasons],
        )
        for result in selected
    ]
    return Page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=page_count(total, page_size),
    )

