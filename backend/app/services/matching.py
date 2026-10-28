from __future__ import annotations

import math
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable, Protocol


TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "at",
    "black",  # common colors are handled as attributes rather than ordinary tokens
    "for",
    "found",
    "in",
    "is",
    "item",
    "lost",
    "my",
    "near",
    "of",
    "on",
    "or",
    "the",
    "this",
    "to",
    "was",
    "with",
}
COLORS = {
    "black",
    "blue",
    "brown",
    "gold",
    "gray",
    "green",
    "grey",
    "orange",
    "pink",
    "purple",
    "red",
    "silver",
    "white",
    "yellow",
}


@dataclass(frozen=True)
class MatchableReport:
    id: uuid.UUID
    report_type: str
    category_id: uuid.UUID
    item_name: str
    description: str
    public_details: str | None
    location_id: uuid.UUID | None
    approximate_location: str | None
    occurred_at: datetime
    image_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class Reason:
    factor: str
    contribution: int
    explanation: str


@dataclass(frozen=True)
class MatchResult:
    candidate_id: uuid.UUID
    score: int
    reasons: tuple[Reason, ...]


class ImageSimilarityProvider(Protocol):
    """Optional future adapter. Implementations return 0..1 or None if unavailable."""

    def similarity(self, left_keys: tuple[str, ...], right_keys: tuple[str, ...]) -> float | None: ...


def to_matchable(report) -> MatchableReport:
    occurred = report.occurred_at
    if occurred.tzinfo is None:
        occurred = occurred.replace(tzinfo=UTC)
    return MatchableReport(
        id=report.id,
        report_type=report.report_type,
        category_id=report.category_id,
        item_name=report.item_name,
        description=report.description,
        public_details=report.public_details,
        location_id=report.location_id,
        approximate_location=report.approximate_location,
        occurred_at=occurred,
        image_keys=tuple(image.storage_key for image in getattr(report, "images", ())),
    )


def tokenize(value: str | None) -> list[str]:
    if not value:
        return []
    return [token for token in TOKEN_RE.findall(value.lower()) if token not in STOP_WORDS]


def weighted_cosine(left: list[str], right: list[str]) -> float:
    if not left or not right:
        return 0.0
    left_counts, right_counts = Counter(left), Counter(right)
    shared = left_counts.keys() & right_counts.keys()
    numerator = sum(left_counts[token] * right_counts[token] for token in shared)
    denominator = math.sqrt(sum(v * v for v in left_counts.values())) * math.sqrt(
        sum(v * v for v in right_counts.values())
    )
    return numerator / denominator if denominator else 0.0


def distinctive_attributes(value: str | None) -> set[str]:
    tokens = set(TOKEN_RE.findall((value or "").lower()))
    attributes = {token for token in tokens if token in COLORS}
    attributes.update(
        token
        for token in tokens
        if any(char.isdigit() for char in token) and len(token) >= 2
    )
    # Unusually long terms often capture brands, engravings, or model names.
    attributes.update(token for token in tokens if len(token) >= 9)
    return attributes


def score_pair(
    source: MatchableReport,
    candidate: MatchableReport,
    image_provider: ImageSimilarityProvider | None = None,
) -> MatchResult:
    if source.report_type == candidate.report_type:
        return MatchResult(
            candidate.id,
            0,
            (Reason("report_type", 0, "Reports must be complementary lost/found types"),),
        )

    reasons: list[Reason] = []
    score = 0.0

    same_category = source.category_id == candidate.category_id
    if same_category:
        score += 30
        reasons.append(Reason("category", 30, "Same item category"))
    else:
        reasons.append(Reason("category", 0, "Different item categories reduce confidence"))

    source_name, candidate_name = tokenize(source.item_name), tokenize(candidate.item_name)
    name_similarity = weighted_cosine(source_name, candidate_name)
    source_text = tokenize(" ".join(filter(None, [source.item_name, source.description, source.public_details])))
    candidate_text = tokenize(
        " ".join(filter(None, [candidate.item_name, candidate.description, candidate.public_details]))
    )
    description_similarity = weighted_cosine(source_text, candidate_text)
    text_points = round(12 * name_similarity + 18 * description_similarity)
    if text_points:
        score += text_points
        reasons.append(
            Reason("description", text_points, "Item names and descriptions share meaningful terms")
        )

    source_attributes = distinctive_attributes(" ".join([source.item_name, source.description]))
    candidate_attributes = distinctive_attributes(" ".join([candidate.item_name, candidate.description]))
    shared_attributes = sorted(source_attributes & candidate_attributes)
    if shared_attributes:
        attribute_points = min(10, 4 + 2 * len(shared_attributes))
        score += attribute_points
        reasons.append(
            Reason(
                "attributes",
                attribute_points,
                "Shared distinctive attributes: " + ", ".join(shared_attributes[:4]),
            )
        )

    location_points = 0
    if source.location_id is not None and source.location_id == candidate.location_id:
        location_points = 15
        location_explanation = "Same campus location"
    else:
        location_similarity = weighted_cosine(
            tokenize(source.approximate_location), tokenize(candidate.approximate_location)
        )
        location_points = round(10 * location_similarity)
        location_explanation = "Approximate locations share meaningful terms"
    if location_points:
        score += location_points
        reasons.append(Reason("location", location_points, location_explanation))

    source_time = source.occurred_at
    candidate_time = candidate.occurred_at
    if source_time.tzinfo is None:
        source_time = source_time.replace(tzinfo=UTC)
    if candidate_time.tzinfo is None:
        candidate_time = candidate_time.replace(tzinfo=UTC)
    delta_days = abs((source_time - candidate_time).total_seconds()) / 86400
    if delta_days <= 1:
        time_points = 15
    elif delta_days <= 3:
        time_points = 12
    elif delta_days <= 7:
        time_points = 9
    elif delta_days <= 30:
        time_points = 5
    elif delta_days <= 90:
        time_points = 2
    else:
        time_points = 0
    if time_points:
        score += time_points
        reasons.append(
            Reason("time", time_points, f"Events occurred about {delta_days:.1f} days apart")
        )

    if image_provider and source.image_keys and candidate.image_keys:
        similarity = image_provider.similarity(source.image_keys, candidate.image_keys)
        if similarity is not None:
            image_points = round(max(0.0, min(1.0, similarity)) * 10)
            score += image_points
            if image_points:
                reasons.append(
                    Reason("image", image_points, "Optional image adapter found visual similarity")
                )

    # Generic text must not overwhelm a category mismatch. This is a safety-oriented heuristic cap.
    if not same_category:
        score = min(score, 44)
    return MatchResult(candidate.id, min(100, round(score)), tuple(reasons))


def rank_candidates(
    source: MatchableReport,
    candidates: Iterable[MatchableReport],
    *,
    minimum_score: int = 0,
    image_provider: ImageSimilarityProvider | None = None,
) -> list[MatchResult]:
    """Score every candidate before ranking/filtering; there is intentionally no pre-ranking cutoff."""

    results = [
        score_pair(source, candidate, image_provider)
        for candidate in candidates
        if candidate.id != source.id and candidate.report_type != source.report_type
    ]
    results.sort(key=lambda result: (-result.score, str(result.candidate_id)))
    return [result for result in results if result.score >= minimum_score]

