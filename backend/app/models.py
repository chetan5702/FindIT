from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Role(str, enum.Enum):
    STUDENT = "student"
    STAFF = "staff"
    ADMIN = "admin"


class ReportType(str, enum.Enum):
    LOST = "lost"
    FOUND = "found"


class ReportStatus(str, enum.Enum):
    OPEN = "open"
    MATCHED = "matched"
    IN_CUSTODY = "in_custody"
    RETURNED = "returned"
    ARCHIVED = "archived"


class ClaimStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"


class CustodyStatus(str, enum.Enum):
    HELD = "held"
    RELEASED = "released"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=Role.STUDENT.value, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )

    reports: Mapped[list[Report]] = relationship(back_populates="reporter")
    claims: Mapped[list[Claim]] = relationship(
        back_populates="claimant", foreign_keys="Claim.claimant_id"
    )

    __table_args__ = (CheckConstraint("role IN ('student','staff','admin')", name="ck_users_role"),)


class AuthActionToken(Base):
    __tablename__ = "auth_action_tokens"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("user_id", "purpose", name="uq_auth_action_user_purpose"),
        CheckConstraint("purpose IN ('verify','reset')", name="ck_auth_action_purpose"),
    )


class AuthRateBucket(Base):
    __tablename__ = "auth_rate_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True, nullable=False)
    csrf_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))

    user: Mapped[User] = relationship()


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Location(TimestampMixin, Base):
    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    building: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    qr_token: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, unique=True, nullable=False)


class Report(TimestampMixin, Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    report_type: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    item_name: Mapped[str] = mapped_column(String(120), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"), index=True
    )
    approximate_location: Mapped[str | None] = mapped_column(String(240))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    public_details: Mapped[str | None] = mapped_column(Text)
    private_details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default=ReportStatus.OPEN.value, index=True, nullable=False
    )

    reporter: Mapped[User] = relationship(back_populates="reports")
    category: Mapped[Category] = relationship()
    location: Mapped[Location | None] = relationship()
    images: Mapped[list[ReportImage]] = relationship(
        back_populates="report", cascade="all, delete-orphan", order_by="ReportImage.created_at"
    )
    claims: Mapped[list[Claim]] = relationship(
        back_populates="found_report",
        foreign_keys="Claim.found_report_id",
    )

    __table_args__ = (
        CheckConstraint("report_type IN ('lost','found')", name="ck_reports_type"),
        CheckConstraint(
            "status IN ('open','matched','in_custody','returned','archived')",
            name="ck_reports_status",
        ),
        Index("ix_reports_browse", "report_type", "status", "occurred_at"),
    )


class ReportImage(Base):
    __tablename__ = "report_images"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True, nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(250))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    report: Mapped[Report] = relationship(back_populates="images")

    __table_args__ = (CheckConstraint("byte_size > 0", name="ck_report_images_size"),)


class Claim(TimestampMixin, Base):
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    found_report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    claimant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    lost_report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reports.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default=ClaimStatus.SUBMITTED.value, index=True, nullable=False
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_reason: Mapped[str | None] = mapped_column(String(1000))

    found_report: Mapped[Report] = relationship(
        back_populates="claims", foreign_keys=[found_report_id]
    )
    claimant: Mapped[User] = relationship(back_populates="claims", foreign_keys=[claimant_id])
    lost_report: Mapped[Report | None] = relationship(foreign_keys=[lost_report_id])
    reviewed_by: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_id])
    evidence: Mapped[list[ClaimEvidence]] = relationship(
        back_populates="claim", cascade="all, delete-orphan", order_by="ClaimEvidence.created_at"
    )
    handover: Mapped[Handover | None] = relationship(back_populates="claim", uselist=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('submitted','under_review','approved','rejected','completed')",
            name="ck_claims_status",
        ),
        CheckConstraint(
            "lost_report_id IS NULL OR lost_report_id <> found_report_id",
            name="ck_claims_distinct_reports",
        ),
    )


Index(
    "uq_claim_active_claimant_report",
    Claim.found_report_id,
    Claim.claimant_id,
    unique=True,
    postgresql_where=Claim.status.in_(["submitted", "under_review", "approved"]),
    sqlite_where=Claim.status.in_(["submitted", "under_review", "approved"]),
)
Index(
    "uq_claim_approved_found_report",
    Claim.found_report_id,
    unique=True,
    postgresql_where=Claim.status.in_(["approved", "completed"]),
    sqlite_where=Claim.status.in_(["approved", "completed"]),
)


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), index=True, nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(20), nullable=False)
    text_content: Mapped[str | None] = mapped_column(Text)
    storage_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    original_name: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(50))
    byte_size: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    claim: Mapped[Claim] = relationship(back_populates="evidence")

    __table_args__ = (
        CheckConstraint("evidence_type IN ('text','image')", name="ck_claim_evidence_type"),
        CheckConstraint(
            "(evidence_type = 'text' AND text_content IS NOT NULL) OR "
            "(evidence_type = 'image' AND storage_key IS NOT NULL)",
            name="ck_claim_evidence_content",
        ),
    )


class CustodyRecord(TimestampMixin, Base):
    __tablename__ = "custody_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    found_report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default=CustodyStatus.HELD.value, index=True, nullable=False
    )
    storage_location: Mapped[str] = mapped_column(String(240), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(1000))
    received_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    found_report: Mapped[Report] = relationship()
    received_by: Mapped[User] = relationship()

    __table_args__ = (CheckConstraint("status IN ('held','released')", name="ck_custody_status"),)


class Handover(Base):
    __tablename__ = "handovers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("claims.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    found_report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    claimant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(String(1000))

    claim: Mapped[Claim] = relationship(back_populates="handover")
    found_report: Mapped[Report] = relationship()
    claimant: Mapped[User] = relationship(foreign_keys=[claimant_id])
    staff: Mapped[User] = relationship(foreign_keys=[staff_id])


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(String(600), nullable=False)
    link: Mapped[str | None] = mapped_column(String(300))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )

    user: Mapped[User] = relationship()


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    metadata_json: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )

    actor: Mapped[User | None] = relationship()
