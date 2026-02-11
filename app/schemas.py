from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DecisionType(str, Enum):
    AUTO_APPROVE = "AUTO_APPROVE"
    REVIEW_OPS = "REVIEW_OPS"
    AUTO_REJECT = "AUTO_REJECT"


class NameMatchCase(BaseModel):
    case_id: str = Field(..., description="Unique id for audit and traceability.")
    bank_name: str = Field(..., min_length=1, description="Name provided by bank records.")
    pan_name: str = Field(..., min_length=1, description="Name from PAN records.")
    model_score: float = Field(
        ..., ge=0.0, le=1.0, description="Existing ML score generated upstream."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata passed through unchanged for downstream systems.",
    )


class TriagePolicy(BaseModel):
    auto_approve_threshold: float = Field(
        default=0.86,
        ge=0.0,
        le=1.0,
        description="Combined score threshold to auto-approve.",
    )
    auto_reject_threshold: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description="Combined score threshold to auto-reject.",
    )
    high_model_score_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="ML score threshold considered high-confidence.",
    )
    low_model_score_threshold: float = Field(
        default=0.40,
        ge=0.0,
        le=1.0,
        description="ML score threshold considered weak-confidence.",
    )


class SimilarityFeatures(BaseModel):
    normalized_bank_name: str
    normalized_pan_name: str
    token_sort_ratio: float = Field(ge=0.0, le=1.0)
    token_set_ratio: float = Field(ge=0.0, le=1.0)
    jaro_winkler: float = Field(ge=0.0, le=1.0)
    levenshtein_similarity: float = Field(ge=0.0, le=1.0)
    partial_ratio: float = Field(ge=0.0, le=1.0)
    token_overlap_shorter: float = Field(ge=0.0, le=1.0)
    token_overlap_overall: float = Field(ge=0.0, le=1.0)
    initial_alignment: float = Field(ge=0.0, le=1.0)
    surname_match: bool
    first_token_match: bool
    subset_match: bool
    model_score: float = Field(ge=0.0, le=1.0)
    combined_score: float = Field(ge=0.0, le=1.0)
    risk_flags: list[str] = Field(default_factory=list)


class CaseDecision(BaseModel):
    case_id: str
    decision: DecisionType
    confidence: float = Field(ge=0.0, le=1.0)
    ops_ticket_required: bool
    reasons: list[str] = Field(default_factory=list)
    features: SimilarityFeatures | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TriageRequest(BaseModel):
    cases: list[NameMatchCase] = Field(min_length=1)
    policy: TriagePolicy = Field(default_factory=TriagePolicy)
    include_features: bool = Field(
        default=True, description="Set false to reduce payload size."
    )


class TriageSummary(BaseModel):
    total_cases: int
    auto_approved: int
    auto_rejected: int
    sent_to_ops: int
    ops_reduction_ratio: float = Field(
        ge=0.0, le=1.0, description="Fraction of cases that avoided ops."
    )


class TriageResponse(BaseModel):
    summary: TriageSummary
    decisions: list[CaseDecision]

