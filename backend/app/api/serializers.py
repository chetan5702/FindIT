import json

from app.models import AuditEvent, Claim, CustodyRecord, Handover, Report, Role, User
from app.schemas import (
    AuditEventOut,
    CategoryOut,
    ClaimOut,
    CustodyOut,
    EvidenceOut,
    HandoverOut,
    LocationOut,
    PublicUserOut,
    ReportImageOut,
    ReportOut,
    ReportSummary,
)


def public_user(user: User | None) -> PublicUserOut | None:
    return PublicUserOut.model_validate(user) if user else None


def image_out(image, report_id) -> ReportImageOut:
    return ReportImageOut(
        id=image.id,
        original_name=image.original_name,
        mime_type=image.mime_type,
        byte_size=image.byte_size,
        alt_text=image.alt_text,
        created_at=image.created_at,
        url=f"/api/v1/reports/{report_id}/images/{image.id}",
    )


def report_summary(report: Report) -> ReportSummary:
    first_image = report.images[0] if report.images else None
    return ReportSummary(
        id=report.id,
        report_type=report.report_type,
        item_name=report.item_name,
        category_id=report.category_id,
        category=CategoryOut.model_validate(report.category),
        location_id=report.location_id,
        location=LocationOut.model_validate(report.location) if report.location else None,
        approximate_location=report.approximate_location,
        occurred_at=report.occurred_at,
        description=report.description,
        public_details=report.public_details,
        status=report.status,
        images=[image_out(image, report.id) for image in report.images],
        image_count=len(report.images),
        thumbnail_url=(
            f"/api/v1/reports/{report.id}/images/{first_image.id}" if first_image else None
        ),
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


def report_out(report: Report, viewer: User) -> ReportOut:
    privileged = viewer.id == report.reporter_id or viewer.role in {
        Role.STAFF.value,
        Role.ADMIN.value,
    }
    summary = report_summary(report)
    return ReportOut(
        **summary.model_dump(),
        private_details=report.private_details if privileged else None,
        reporter=public_user(report.reporter) if privileged else None,
        is_owner=viewer.id == report.reporter_id,
        can_edit=(
            (viewer.id == report.reporter_id or viewer.role == Role.ADMIN.value)
            and report.status not in {"returned", "archived"}
        ),
        can_claim=(
            report.report_type == "found"
            and viewer.id != report.reporter_id
            and report.status in {"open", "matched", "in_custody"}
        ),
    )


def evidence_out(evidence, claim_id) -> EvidenceOut:
    return EvidenceOut(
        id=evidence.id,
        evidence_type=evidence.evidence_type,
        text_content=evidence.text_content,
        original_name=evidence.original_name,
        mime_type=evidence.mime_type,
        byte_size=evidence.byte_size,
        created_at=evidence.created_at,
        url=(
            f"/api/v1/claims/{claim_id}/evidence/{evidence.id}"
            if evidence.evidence_type == "image"
            else None
        ),
    )


def claim_out(claim: Claim) -> ClaimOut:
    proof = next(
        (item.text_content for item in claim.evidence if item.evidence_type == "text"), None
    )
    return ClaimOut(
        id=claim.id,
        found_report_id=claim.found_report_id,
        found_report=report_summary(claim.found_report),
        lost_report_id=claim.lost_report_id,
        lost_report=report_summary(claim.lost_report) if claim.lost_report else None,
        claimant_id=claim.claimant_id,
        claimant=public_user(claim.claimant),
        status=claim.status,
        evidence=[evidence_out(item, claim.id) for item in claim.evidence],
        reviewed_by=public_user(claim.reviewed_by),
        reviewed_at=claim.reviewed_at,
        decision_reason=claim.decision_reason,
        review_reason=claim.decision_reason,
        proof_text=proof,
        created_at=claim.created_at,
        updated_at=claim.updated_at,
    )


def custody_out(custody: CustodyRecord) -> CustodyOut:
    return CustodyOut(
        id=custody.id,
        report_id=custody.found_report_id,
        report=report_summary(custody.found_report),
        found_report=report_summary(custody.found_report),
        status=custody.status,
        storage_location=custody.storage_location,
        notes=custody.notes,
        received_by=public_user(custody.received_by),
        received_at=custody.received_at,
        released_at=custody.released_at,
        created_at=custody.created_at,
        updated_at=custody.updated_at,
    )


def handover_out(handover: Handover) -> HandoverOut:
    return HandoverOut(
        id=handover.id,
        claim_id=handover.claim_id,
        found_report=report_summary(handover.found_report),
        claimant=public_user(handover.claimant),
        staff=public_user(handover.staff),
        completed_at=handover.completed_at,
        handed_over_at=handover.completed_at,
        notes=handover.notes,
    )


def audit_out(event: AuditEvent) -> AuditEventOut:
    try:
        metadata = json.loads(event.metadata_json or "{}")
    except json.JSONDecodeError:
        metadata = {}
    return AuditEventOut(
        id=event.id,
        actor=public_user(event.actor),
        action=event.action,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        metadata=metadata,
        ip_address=event.ip_address,
        created_at=event.created_at,
    )

