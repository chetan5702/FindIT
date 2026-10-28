from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.claims import CLAIM_LOADS, load_claim
from app.api.reports import REPORT_LOADS
from app.api.serializers import claim_out, custody_out, handover_out, report_summary
from app.database import get_db
from app.dependencies import require_staff, require_staff_csrf
from app.errors import APIError
from app.models import (
    Claim,
    ClaimStatus,
    CustodyRecord,
    CustodyStatus,
    Handover,
    Report,
    User,
)
from app.schemas import (
    ClaimOut,
    ClaimStatusUpdate,
    CustodyCreate,
    CustodyOut,
    CustodyUpdate,
    HandoverCreate,
    HandoverOut,
    Page,
    StaffDashboardOut,
)
from app.services.common import audit, notify, page_count


router = APIRouter(prefix="/staff", tags=["staff"])

CUSTODY_LOADS = (
    selectinload(CustodyRecord.received_by),
    selectinload(CustodyRecord.found_report).selectinload(Report.category),
    selectinload(CustodyRecord.found_report).selectinload(Report.location),
    selectinload(CustodyRecord.found_report).selectinload(Report.images),
)
HANDOVER_LOADS = (
    selectinload(Handover.claim),
    selectinload(Handover.claimant),
    selectinload(Handover.staff),
    selectinload(Handover.found_report).selectinload(Report.category),
    selectinload(Handover.found_report).selectinload(Report.location),
    selectinload(Handover.found_report).selectinload(Report.images),
)


@router.get("/dashboard", response_model=StaffDashboardOut)
def staff_dashboard(
    staff: User = Depends(require_staff), db: Session = Depends(get_db)
) -> StaffDashboardOut:
    incoming_found = db.scalar(
        select(func.count(Report.id)).where(
            Report.report_type == "found", Report.status.in_(["open", "matched"])
        )
    ) or 0
    in_custody = db.scalar(
        select(func.count(CustodyRecord.id)).where(CustodyRecord.status == "held")
    ) or 0
    pending_claims = db.scalar(
        select(func.count(Claim.id)).where(Claim.status.in_(["submitted", "under_review"]))
    ) or 0
    completed_returns = db.scalar(
        select(func.count(Handover.id))
    ) or 0
    recent_claims = list(
        db.scalars(
            select(Claim)
            .options(*CLAIM_LOADS)
            .order_by(Claim.created_at.desc())
            .limit(5)
        )
    )
    recent_found = list(
        db.scalars(
            select(Report)
            .where(Report.report_type == "found", Report.status != "archived")
            .options(*REPORT_LOADS)
            .order_by(Report.created_at.desc())
            .limit(5)
        )
    )
    return StaffDashboardOut(
        incoming_found=incoming_found,
        in_custody=in_custody,
        pending_claims=pending_claims,
        completed_returns=completed_returns,
        recent_claims=[claim_out(claim) for claim in recent_claims],
        recent_found=[report_summary(report) for report in recent_found],
    )


@router.patch("/claims/{claim_id}/status", response_model=ClaimOut)
def review_claim(
    claim_id: uuid.UUID,
    payload: ClaimStatusUpdate,
    staff: User = Depends(require_staff_csrf),
    db: Session = Depends(get_db),
) -> ClaimOut:
    base_claim = db.get(Claim, claim_id)
    if base_claim is None:
        raise APIError(404, "claim_not_found", "Claim not found")

    if payload.status == ClaimStatus.APPROVED.value:
        # The found report is the serialization lock for competing approvals.
        report = db.scalar(
            select(Report).where(Report.id == base_claim.found_report_id).with_for_update().execution_options(populate_existing=True)
        )
        claims = list(
            db.scalars(
                select(Claim)
                .where(Claim.found_report_id == base_claim.found_report_id)
                .order_by(Claim.id)
                .with_for_update().execution_options(populate_existing=True)
            )
        )
        claim = next((item for item in claims if item.id == claim_id), None)
        if claim is None:
            raise APIError(404, "claim_not_found", "Claim not found")
        if claim.status != ClaimStatus.UNDER_REVIEW.value:
            raise APIError(
                409,
                "invalid_claim_transition",
                "Only a claim under review can be approved",
            )
        competing_approved = next(
            (
                item
                for item in claims
                if item.id != claim.id and item.status in {"approved", "completed"}
            ),
            None,
        )
        if competing_approved:
            raise APIError(409, "claim_conflict", "Another claim is already approved")
        now = datetime.now(UTC)
        for other in claims:
            if other.id != claim.id and other.status in {"submitted", "under_review"}:
                other.status = ClaimStatus.REJECTED.value
                other.reviewed_by_id = staff.id
                other.reviewed_at = now
                other.decision_reason = "Another ownership claim was approved."
                notify(
                    db,
                    other.claimant_id,
                    "claim_decision",
                    "Ownership claim not approved",
                    "Another verified claim for this item was approved.",
                    f"/app/claims/{other.id}",
                )
        claim.status = ClaimStatus.APPROVED.value
        claim.reviewed_by_id = staff.id
        claim.reviewed_at = now
        claim.decision_reason = payload.reason.strip() if payload.reason else None
        if report and report.status == "open":
            report.status = "matched"
    else:
        claim = db.scalar(select(Claim).where(Claim.id == claim_id).with_for_update().execution_options(populate_existing=True))
        if claim is None:
            raise APIError(404, "claim_not_found", "Claim not found")
        transitions = {
            ClaimStatus.SUBMITTED.value: {
                ClaimStatus.UNDER_REVIEW.value,
                ClaimStatus.REJECTED.value,
            },
            ClaimStatus.UNDER_REVIEW.value: {ClaimStatus.REJECTED.value},
        }
        if payload.status not in transitions.get(claim.status, set()):
            raise APIError(
                409,
                "invalid_claim_transition",
                f"A {claim.status} claim cannot transition to {payload.status}",
            )
        claim.status = payload.status
        claim.reviewed_by_id = staff.id
        claim.reviewed_at = datetime.now(UTC)
        claim.decision_reason = payload.reason.strip() if payload.reason else None

    audit(
        db,
        f"claim.{payload.status}",
        "claim",
        claim.id,
        actor=staff,
        metadata={"from_staff_review": True},
    )
    notify(
        db,
        claim.claimant_id,
        "claim_review" if payload.status == "under_review" else "claim_decision",
        "Ownership claim updated",
        f"Your claim is now {payload.status.replace('_', ' ')}.",
        f"/app/claims/{claim.id}",
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise APIError(409, "claim_conflict", "Another claim was approved concurrently") from None
    return claim_out(load_claim(db, claim.id))


@router.get("/custody", response_model=Page[CustodyOut])
def list_custody(
    custody_status: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    staff: User = Depends(require_staff),
    db: Session = Depends(get_db),
) -> Page[CustodyOut]:
    filters = []
    if custody_status:
        if custody_status not in {"held", "released"}:
            raise APIError(422, "invalid_status", "Unknown custody status")
        filters.append(CustodyRecord.status == custody_status)
    total = db.scalar(select(func.count(CustodyRecord.id)).where(*filters)) or 0
    records = list(
        db.scalars(
            select(CustodyRecord)
            .where(*filters)
            .options(*CUSTODY_LOADS)
            .order_by(CustodyRecord.received_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return Page(
        items=[custody_out(item) for item in records],
        total=total,
        page=page,
        page_size=page_size,
        pages=page_count(total, page_size),
    )


@router.post("/custody", response_model=CustodyOut, status_code=status.HTTP_201_CREATED)
def take_custody(
    payload: CustodyCreate,
    staff: User = Depends(require_staff_csrf),
    db: Session = Depends(get_db),
) -> CustodyOut:
    report = db.scalar(select(Report).where(Report.id == payload.report_id).with_for_update().execution_options(populate_existing=True))
    if report is None or report.report_type != "found":
        raise APIError(404, "found_report_not_found", "Found-item report not found")
    if report.status in {"returned", "archived"}:
        raise APIError(409, "report_unavailable", "This report cannot enter custody")
    if db.scalar(select(CustodyRecord.id).where(CustodyRecord.found_report_id == report.id)):
        raise APIError(409, "custody_exists", "A custody record already exists for this report")
    custody = CustodyRecord(
        found_report_id=report.id,
        status=CustodyStatus.HELD.value,
        storage_location=payload.storage_location.strip(),
        notes=payload.notes.strip() if payload.notes else None,
        received_by_id=staff.id,
    )
    db.add(custody)
    report.status = "in_custody"
    db.flush()
    audit(db, "custody.received", "custody_record", custody.id, actor=staff)
    notify(
        db,
        report.reporter_id,
        "custody_update",
        "Item received by campus staff",
        f"Campus staff recorded custody of {report.item_name}.",
        f"/app/reports/{report.id}",
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise APIError(409, "custody_exists", "A custody record already exists") from None
    custody = db.scalar(
        select(CustodyRecord).where(CustodyRecord.id == custody.id).options(*CUSTODY_LOADS)
    )
    return custody_out(custody)


@router.patch("/custody/{custody_id}", response_model=CustodyOut)
def update_custody(
    custody_id: uuid.UUID,
    payload: CustodyUpdate,
    staff: User = Depends(require_staff_csrf),
    db: Session = Depends(get_db),
) -> CustodyOut:
    custody = db.scalar(
        select(CustodyRecord).where(CustodyRecord.id == custody_id).with_for_update().execution_options(populate_existing=True)
    )
    if custody is None:
        raise APIError(404, "custody_not_found", "Custody record not found")
    if custody.status == CustodyStatus.RELEASED.value:
        raise APIError(409, "custody_locked", "Released custody records cannot be changed")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(custody, key, value.strip() if isinstance(value, str) else value)
    audit(
        db,
        "custody.updated",
        "custody_record",
        custody.id,
        actor=staff,
        metadata={"fields": sorted(changes)},
    )
    db.commit()
    custody = db.scalar(
        select(CustodyRecord).where(CustodyRecord.id == custody.id).options(*CUSTODY_LOADS)
    )
    return custody_out(custody)


@router.post("/claims/{claim_id}/handover", response_model=HandoverOut)
def complete_handover(
    claim_id: uuid.UUID,
    payload: HandoverCreate,
    staff: User = Depends(require_staff_csrf),
    db: Session = Depends(get_db),
) -> HandoverOut:
    base_claim = db.get(Claim, claim_id)
    if base_claim is None:
        raise APIError(404, "claim_not_found", "Claim not found")
    report = db.scalar(
        select(Report).where(Report.id == base_claim.found_report_id).with_for_update().execution_options(populate_existing=True)
    )
    claim = db.scalar(select(Claim).where(Claim.id == claim_id).with_for_update().execution_options(populate_existing=True))
    custody = db.scalar(
        select(CustodyRecord)
        .where(CustodyRecord.found_report_id == base_claim.found_report_id)
        .with_for_update().execution_options(populate_existing=True)
    )
    if claim is None or report is None:
        raise APIError(404, "claim_not_found", "Claim not found")
    if claim.status != ClaimStatus.APPROVED.value:
        raise APIError(409, "invalid_claim_transition", "Only an approved claim can be completed")
    if custody is None or custody.status != CustodyStatus.HELD.value:
        raise APIError(
            409,
            "custody_required",
            "The item must be recorded in staff custody before handover",
        )
    if db.scalar(select(Handover.id).where(Handover.found_report_id == report.id)):
        raise APIError(409, "handover_exists", "This item has already been handed over")
    completed_at = datetime.now(UTC)
    handover = Handover(
        claim_id=claim.id,
        found_report_id=report.id,
        claimant_id=claim.claimant_id,
        staff_id=staff.id,
        completed_at=completed_at,
        notes=payload.notes.strip() if payload.notes else None,
    )
    db.add(handover)
    claim.status = ClaimStatus.COMPLETED.value
    report.status = "returned"
    # Once the matching found item is returned, its claimant's linked lost
    # report must stop appearing as open to future matching and searches.
    if claim.lost_report_id:
        lost_report = db.scalar(
            select(Report).where(Report.id == claim.lost_report_id).with_for_update().execution_options(populate_existing=True)
        )
        if lost_report is not None:
            lost_report.status = "returned"
    custody.status = CustodyStatus.RELEASED.value
    custody.released_at = completed_at
    db.flush()
    audit(
        db,
        "handover.completed",
        "handover",
        handover.id,
        actor=staff,
        metadata={"claim_id": claim.id, "claimant_id": claim.claimant_id},
    )
    notify(
        db,
        claim.claimant_id,
        "handover_completed",
        "Item handover completed",
        f"Campus staff recorded the return of {report.item_name} to you.",
        f"/app/claims/{claim.id}",
    )
    if report.reporter_id != claim.claimant_id:
        notify(
            db,
            report.reporter_id,
            "handover_completed",
            "Found item returned",
            f"The {report.item_name} you reported was returned to its verified owner.",
            f"/app/reports/{report.id}",
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise APIError(409, "handover_exists", "This item was handed over concurrently") from None
    handover = db.scalar(
        select(Handover).where(Handover.id == handover.id).options(*HANDOVER_LOADS)
    )
    return handover_out(handover)


@router.get("/handovers", response_model=Page[HandoverOut])
def list_handovers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    staff: User = Depends(require_staff),
    db: Session = Depends(get_db),
) -> Page[HandoverOut]:
    total = db.scalar(select(func.count(Handover.id))) or 0
    handovers = list(
        db.scalars(
            select(Handover)
            .options(*HANDOVER_LOADS)
            .order_by(Handover.completed_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return Page(
        items=[handover_out(item) for item in handovers],
        total=total,
        page=page,
        page_size=page_size,
        pages=page_count(total, page_size),
    )

