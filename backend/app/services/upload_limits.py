from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.config import Settings
from app.errors import APIError
from app.models import Claim, ClaimEvidence, Report, ReportImage, User


def lock_uploader(db: Session, user_id) -> None:
    # Both upload paths acquire this lock before report/claim locks.
    # NO KEY UPDATE serializes quota admissions without blocking FK references
    # inserted by handovers/notifications while they hold a report/claim lock.
    db.scalar(select(User).where(User.id == user_id).with_for_update(key_share=True))


def check_upload_quota(db: Session, user_id, size: int, settings: Settings) -> None:
    reports = (
        db.scalar(
            select(func.coalesce(func.sum(ReportImage.byte_size), 0))
            .join(Report, Report.id == ReportImage.report_id)
            .where(Report.reporter_id == user_id)
        )
        or 0
    )
    evidence = (
        db.scalar(
            select(func.coalesce(func.sum(ClaimEvidence.byte_size), 0))
            .join(Claim, Claim.id == ClaimEvidence.claim_id)
            .where(Claim.claimant_id == user_id)
        )
        or 0
    )
    if reports + evidence + size > settings.max_user_upload_bytes:
        raise APIError(413, "upload_quota", "Your total upload storage limit has been reached")
