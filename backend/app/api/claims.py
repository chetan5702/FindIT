from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.serializers import claim_out, evidence_out
from app.config import Settings, get_settings
from app.database import get_db
from app.dependencies import Principal, get_current_user, require_csrf
from app.errors import APIError
from app.models import Claim, ClaimEvidence, ClaimStatus, Report, Role, User
from app.schemas import ClaimCreate, ClaimOut, EvidenceOut, Page
from app.services.common import audit, notify, page_count
from app.storage import EXTENSIONS, LocalStorage, validate_image
from app.services.upload_limits import lock_uploader, check_upload_quota


router = APIRouter(tags=["claims"])

CLAIM_LOADS = (
    selectinload(Claim.claimant),
    selectinload(Claim.reviewed_by),
    selectinload(Claim.evidence),
    selectinload(Claim.found_report).selectinload(Report.category),
    selectinload(Claim.found_report).selectinload(Report.location),
    selectinload(Claim.found_report).selectinload(Report.images),
    selectinload(Claim.lost_report).selectinload(Report.category),
    selectinload(Claim.lost_report).selectinload(Report.location),
    selectinload(Claim.lost_report).selectinload(Report.images),
)


def load_claim(db: Session, claim_id: uuid.UUID, *, for_update: bool = False) -> Claim:
    statement = select(Claim).where(Claim.id == claim_id).options(*CLAIM_LOADS)
    if for_update:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    claim = db.scalar(statement)
    if claim is None:
        raise APIError(404, "claim_not_found", "Claim not found")
    return claim


def ensure_claim_access(claim: Claim, user: User) -> None:
    if user.id != claim.claimant_id and user.role not in {Role.STAFF.value, Role.ADMIN.value}:
        raise APIError(403, "forbidden", "You cannot view this claim")


@router.post(
    "/reports/{found_report_id}/claims",
    response_model=ClaimOut,
    status_code=status.HTTP_201_CREATED,
)
def create_claim(
    found_report_id: uuid.UUID,
    payload: ClaimCreate,
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> ClaimOut:
    found_report = db.scalar(
        select(Report).where(Report.id == found_report_id).with_for_update()
    )
    if found_report is None or found_report.report_type != "found":
        raise APIError(404, "found_report_not_found", "Found-item report not found")
    if found_report.reporter_id == principal.user.id:
        raise APIError(409, "self_claim", "You cannot claim an item that you reported")
    if found_report.status not in {"open", "matched", "in_custody"}:
        raise APIError(409, "report_unavailable", "This item is no longer available to claim")

    lost_report = None
    if payload.lost_report_id:
        lost_report = db.get(Report, payload.lost_report_id)
        if (
            lost_report is None
            or lost_report.report_type != "lost"
            or lost_report.reporter_id != principal.user.id
        ):
            raise APIError(
                422,
                "invalid_lost_report",
                "The linked lost report must be your own lost-item report",
            )
        if lost_report.status in {"returned", "archived"}:
            raise APIError(409, "lost_report_locked", "The linked lost report is closed")

    duplicate = db.scalar(
        select(Claim.id).where(
            Claim.found_report_id == found_report.id,
            Claim.claimant_id == principal.user.id,
            Claim.status.in_(["submitted", "under_review", "approved"]),
        )
    )
    if duplicate:
        raise APIError(409, "duplicate_claim", "You already have an active claim for this item")
    approved = db.scalar(
        select(Claim.id).where(
            Claim.found_report_id == found_report.id,
            Claim.status.in_(["approved", "completed"]),
        )
    )
    if approved:
        raise APIError(409, "claim_conflict", "This item already has an approved claim")

    claim = Claim(
        found_report_id=found_report.id,
        claimant_id=principal.user.id,
        lost_report_id=lost_report.id if lost_report else None,
        status=ClaimStatus.SUBMITTED.value,
    )
    db.add(claim)
    db.flush()
    db.add(
        ClaimEvidence(
            claim_id=claim.id,
            evidence_type="text",
            text_content=payload.proof_text.strip(),
        )
    )
    audit(db, "claim.submitted", "claim", claim.id, actor=principal.user)
    staff_ids = list(
        db.scalars(
            select(User.id).where(
                User.role.in_([Role.STAFF.value, Role.ADMIN.value]), User.is_active.is_(True)
            )
        )
    )
    for staff_id in staff_ids:
        notify(
            db,
            staff_id,
            "claim_submitted",
            "Ownership claim needs review",
            f"A claim for {found_report.item_name} is awaiting staff review.",
            f"/staff/claims/{claim.id}",
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise APIError(409, "duplicate_claim", "An active claim already exists") from None
    return claim_out(load_claim(db, claim.id))


@router.get("/claims", response_model=Page[ClaimOut])
def list_claims(
    claim_status: str | None = Query(default=None, alias="status"),
    found_report_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[ClaimOut]:
    filters = []
    if user.role not in {Role.STAFF.value, Role.ADMIN.value}:
        filters.append(Claim.claimant_id == user.id)
    if claim_status:
        if claim_status not in {item.value for item in ClaimStatus}:
            raise APIError(422, "invalid_status", "Unknown claim status")
        filters.append(Claim.status == claim_status)
    if found_report_id:
        filters.append(Claim.found_report_id == found_report_id)
    total = db.scalar(select(func.count(Claim.id)).where(*filters)) or 0
    claims = list(
        db.scalars(
            select(Claim)
            .where(*filters)
            .options(*CLAIM_LOADS)
            .order_by(Claim.created_at.desc(), Claim.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return Page(
        items=[claim_out(claim) for claim in claims],
        total=total,
        page=page,
        page_size=page_size,
        pages=page_count(total, page_size),
    )


@router.get("/claims/{claim_id}", response_model=ClaimOut)
def get_claim(
    claim_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClaimOut:
    claim = load_claim(db, claim_id)
    ensure_claim_access(claim, user)
    return claim_out(claim)


@router.post(
    "/claims/{claim_id}/evidence",
    response_model=EvidenceOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_claim_evidence(
    claim_id: uuid.UUID,
    file: UploadFile = File(...),
    principal: Principal = Depends(require_csrf),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> EvidenceOut:
    lock_uploader(db, principal.user.id)
    claim = load_claim(db, claim_id, for_update=True)
    if claim.claimant_id != principal.user.id:
        raise APIError(403, "forbidden", "Only the claimant can add ownership evidence")
    if claim.status not in {"submitted", "under_review"}:
        raise APIError(409, "claim_locked", "Evidence is locked after a claim decision")
    if sum(item.evidence_type == "image" for item in claim.evidence) >= settings.max_claim_evidence_images:
        raise APIError(409, "evidence_limit", "The claim already has the maximum number of evidence images")
    content = await file.read(settings.max_upload_bytes + 1)
    validated = validate_image(content, file.content_type, settings.max_upload_bytes)
    check_upload_quota(db, principal.user.id, validated.byte_size, settings)
    storage = LocalStorage(settings.media_root)
    storage_key = storage.save(
        f"claim-{claim.id}", validated.content, EXTENSIONS[validated.mime_type]
    )
    evidence = ClaimEvidence(
        claim_id=claim.id,
        evidence_type="image",
        storage_key=storage_key,
        original_name=(file.filename or "evidence")[:255],
        mime_type=validated.mime_type,
        byte_size=validated.byte_size,
        sha256=validated.sha256,
    )
    db.add(evidence)
    audit(db, "claim.evidence_added", "claim", claim.id, actor=principal.user)
    try:
        db.commit()
    except Exception:
        storage.delete(storage_key)
        raise
    db.refresh(evidence)
    return evidence_out(evidence, claim.id)


@router.get("/claims/{claim_id}/evidence/{evidence_id}")
def get_claim_evidence(
    claim_id: uuid.UUID,
    evidence_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    claim = load_claim(db, claim_id)
    ensure_claim_access(claim, user)
    evidence = db.scalar(
        select(ClaimEvidence).where(
            ClaimEvidence.id == evidence_id,
            ClaimEvidence.claim_id == claim.id,
            ClaimEvidence.evidence_type == "image",
        )
    )
    if evidence is None or not evidence.storage_key:
        raise APIError(404, "evidence_not_found", "Evidence not found")
    path = LocalStorage(settings.media_root).path_for(evidence.storage_key)
    if not path.is_file():
        raise APIError(404, "evidence_not_found", "Evidence not found")
    return FileResponse(
        path,
        media_type=evidence.mime_type or "application/octet-stream",
        headers={"Cache-Control": "no-store"},
    )

