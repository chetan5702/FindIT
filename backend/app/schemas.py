from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Annotated, ClassVar, Generic, Literal, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


T = TypeVar("T")


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(APIModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class UserOut(APIModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: Literal["student", "staff", "admin"]
    is_active: bool
    email_verified: bool
    created_at: datetime


class PublicUserOut(APIModel):
    id: uuid.UUID
    full_name: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)
    ]

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValueError("Password must include at least one letter and one number")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class AuthResponse(BaseModel):
    user: UserOut | None = None
    verification_required: bool = False
    message: str | None = None


class EmailActionRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return str(value).lower()


class TokenRequest(BaseModel):
    token: str = Field(min_length=32, max_length=128)


class PasswordResetRequest(TokenRequest):
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def password_policy(cls, value):
        return RegisterRequest.strong_password(value)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def password_policy(cls, value):
        return RegisterRequest.strong_password(value)


class ProfileUpdate(BaseModel):
    full_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)
    ]

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return " ".join(value.split())


class PatchModel(BaseModel):
    non_nullable_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def reject_explicit_null(self):
        for field in self.non_nullable_fields & self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class CategoryCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
    description: str | None = Field(default=None, max_length=300)


class CategoryUpdate(PatchModel):
    non_nullable_fields = frozenset(("name", "is_active"))
    name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)] | None
    ) = None
    description: str | None = Field(default=None, max_length=300)
    is_active: bool | None = None


class CategoryOut(APIModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    is_active: bool


class LocationCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    description: str | None = Field(default=None, max_length=500)
    building: str | None = Field(default=None, max_length=120)


class LocationUpdate(PatchModel):
    non_nullable_fields = frozenset(("name", "is_active"))
    name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
        | None
    ) = None
    description: str | None = Field(default=None, max_length=500)
    building: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None


class LocationOut(APIModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    building: str | None
    is_active: bool


class LocationAdminOut(LocationOut):
    qr_token: uuid.UUID
    reporting_url: str


class ReportImageOut(APIModel):
    id: uuid.UUID
    original_name: str
    mime_type: str
    byte_size: int
    alt_text: str | None
    created_at: datetime
    url: str


ReportItemName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)
]
ReportDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=10, max_length=4000)
]


class ReportCreate(BaseModel):
    report_type: Literal["lost", "found"]
    item_name: ReportItemName
    category_id: uuid.UUID
    description: ReportDescription
    approximate_location: str | None = Field(default=None, max_length=240)
    location_id: uuid.UUID | None = None
    occurred_at: datetime
    public_details: str | None = Field(default=None, max_length=3000)
    private_details: str | None = Field(default=None, max_length=3000)

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        if value.astimezone(UTC) > datetime.now(UTC).replace(microsecond=0):
            raise ValueError("occurred_at cannot be in the future")
        return value


class ReportUpdate(PatchModel):
    non_nullable_fields = frozenset(("item_name", "category_id", "description", "occurred_at"))
    item_name: ReportItemName | None = None
    category_id: uuid.UUID | None = None
    description: ReportDescription | None = None
    approximate_location: str | None = Field(default=None, max_length=240)
    location_id: uuid.UUID | None = None
    occurred_at: datetime | None = None
    public_details: str | None = Field(default=None, max_length=3000)
    private_details: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="after")
    def forbid_null_required_fields(self):
        # PATCH must not erase fields that are non-nullable at the database layer.
        if "item_name" in self.model_fields_set and self.item_name is None:
            raise ValueError("item_name cannot be null")
        if "description" in self.model_fields_set and self.description is None:
            raise ValueError("description cannot be null")
        if "category_id" in self.model_fields_set and self.category_id is None:
            raise ValueError("category_id cannot be null")
        return self

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        if value is not None and value.astimezone(UTC) > datetime.now(UTC).replace(microsecond=0):
            raise ValueError("occurred_at cannot be in the future")
        return value


class ReportSummary(APIModel):
    id: uuid.UUID
    report_type: Literal["lost", "found"]
    item_name: str
    category_id: uuid.UUID
    category: CategoryOut
    location_id: uuid.UUID | None
    location: LocationOut | None
    approximate_location: str | None
    occurred_at: datetime
    description: str
    public_details: str | None
    status: str
    images: list[ReportImageOut]
    image_count: int
    thumbnail_url: str | None
    created_at: datetime
    updated_at: datetime


class ReportOut(ReportSummary):
    private_details: str | None = None
    reporter: PublicUserOut | None = None
    is_owner: bool
    can_edit: bool
    can_claim: bool


class MatchReason(BaseModel):
    factor: str
    contribution: int
    explanation: str


class MatchOut(BaseModel):
    report: ReportSummary
    score: int = Field(ge=0, le=100)
    score_kind: Literal["heuristic"] = "heuristic"
    reasons: list[MatchReason]


class ClaimCreate(BaseModel):
    proof_text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=20, max_length=5000)
    ]
    lost_report_id: uuid.UUID | None = None


class EvidenceOut(APIModel):
    id: uuid.UUID
    evidence_type: Literal["text", "image"]
    text_content: str | None
    original_name: str | None
    mime_type: str | None
    byte_size: int | None
    created_at: datetime
    url: str | None = None


class ClaimOut(APIModel):
    id: uuid.UUID
    found_report_id: uuid.UUID
    found_report: ReportSummary
    lost_report_id: uuid.UUID | None
    lost_report: ReportSummary | None
    claimant_id: uuid.UUID
    claimant: PublicUserOut
    status: Literal["submitted", "under_review", "approved", "rejected", "completed"]
    evidence: list[EvidenceOut]
    reviewed_by: PublicUserOut | None
    reviewed_at: datetime | None
    decision_reason: str | None
    review_reason: str | None
    proof_text: str | None
    created_at: datetime
    updated_at: datetime


class ClaimStatusUpdate(BaseModel):
    status: Literal["under_review", "approved", "rejected"]
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_rejection_reason(self):
        if self.status == "rejected" and not (self.reason and self.reason.strip()):
            raise ValueError("A reason is required when rejecting a claim")
        return self


class CustodyCreate(BaseModel):
    report_id: uuid.UUID
    storage_location: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=240)
    ]
    notes: str | None = Field(default=None, max_length=1000)


class CustodyUpdate(PatchModel):
    non_nullable_fields = frozenset(("storage_location",))
    storage_location: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=240)]
        | None
    ) = None
    notes: str | None = Field(default=None, max_length=1000)


class CustodyOut(APIModel):
    id: uuid.UUID
    report_id: uuid.UUID
    report: ReportSummary
    found_report: ReportSummary
    status: Literal["held", "released"]
    storage_location: str
    notes: str | None
    received_by: PublicUserOut
    received_at: datetime
    released_at: datetime | None
    created_at: datetime
    updated_at: datetime


class HandoverCreate(BaseModel):
    notes: str | None = Field(default=None, max_length=1000)


class HandoverOut(APIModel):
    id: uuid.UUID
    claim_id: uuid.UUID
    found_report: ReportSummary
    claimant: PublicUserOut
    staff: PublicUserOut
    completed_at: datetime
    handed_over_at: datetime
    notes: str | None


class NotificationOut(APIModel):
    id: uuid.UUID
    kind: str
    title: str
    body: str
    message: str
    link: str | None
    action_url: str | None
    read_at: datetime | None
    created_at: datetime


class UnreadCount(BaseModel):
    unread: int


class AdminUserUpdate(PatchModel):
    non_nullable_fields = frozenset(("role", "is_active"))
    role: Literal["student", "staff", "admin"] | None = None
    is_active: bool | None = None


class ReportStatusUpdate(BaseModel):
    status: Literal["open", "matched", "in_custody", "returned", "archived"]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class AuditEventOut(APIModel):
    id: uuid.UUID
    actor: PublicUserOut | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    metadata: dict
    ip_address: str | None
    created_at: datetime


class DashboardMetrics(BaseModel):
    open_lost_reports: int = 0
    open_found_reports: int = 0
    items_in_custody: int = 0
    pending_claims: int = 0
    approved_claims: int = 0
    completed_returns: int = 0
    registered_students: int = 0
    active_staff: int = 0


class StaffDashboardOut(BaseModel):
    incoming_found: int
    in_custody: int
    pending_claims: int
    completed_returns: int
    recent_claims: list[ClaimOut]
    recent_found: list[ReportSummary]


class AdminDashboardOut(BaseModel):
    users: int
    active_reports: int
    staff: int
    returns: int
    categories: int
    locations: int
    reports_by_status: dict[str, int]


class HealthOut(BaseModel):
    status: Literal["ok"]
    database: Literal["ok"]
    version: str
