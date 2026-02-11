from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from name_match_service.decision_engine import Decision


class PartialAcceptRequest(BaseModel):
    bank_name: str = Field(min_length=1, description="Name from bank record")
    pan_name: str = Field(min_length=1, description="Name from PAN record")
    ml_score: float | None = Field(
        default=None,
        description="Model score in [0,1] or [0,100]",
    )
    request_id: str | None = Field(
        default=None,
        description="Optional client-provided id for traceability",
    )
    metadata: dict[str, Any] | None = None


class DecisionFeatures(BaseModel):
    bank_normalized: str
    pan_normalized: str
    bank_tokens: list[str]
    pan_tokens: list[str]
    token_set_score: float
    token_sort_score: float
    jaro_winkler_score: float
    lexical_score: float
    ml_score: float
    blended_score: float
    soft_coverage: float
    first_token_conflict: bool
    first_token_match: bool
    surname_match: bool
    exact_match: bool
    unmatched_pan_tokens: list[str]
    unmatched_bank_tokens: list[str]


class PartialAcceptDecisionResponse(BaseModel):
    request_id: str | None = None
    decision: Decision
    confidence: float
    reason_codes: list[str]
    features: DecisionFeatures
    ops_ticket_required: bool


class BatchDecisionRequest(BaseModel):
    items: list[PartialAcceptRequest] = Field(min_length=1, max_length=1000)


class BatchDecisionResponse(BaseModel):
    total_items: int
    auto_accept_count: int
    auto_reject_count: int
    sent_to_ops_count: int
    decisions: list[PartialAcceptDecisionResponse]

