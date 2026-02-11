"""FastAPI app exposing partial-accept review endpoints."""

from __future__ import annotations

import os
from collections import Counter
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from partial_accepts_service.policy import Decision, PolicyConfig
from partial_accepts_service.service import PartialAcceptReviewService, ReviewOutcome


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


class ReviewRequest(BaseModel):
    bank_name: str = Field(min_length=1, description="Name from bank/KYC source")
    pan_name: str = Field(min_length=1, description="Name from PAN source")
    model_score: float | None = Field(default=None, ge=0.0, le=1.0)
    request_id: str | None = Field(default=None)
    metadata: dict[str, Any] | None = None


class ReviewResponse(BaseModel):
    request_id: str | None
    bank_name: str
    pan_name: str
    normalized_bank_name: str
    normalized_pan_name: str
    decision: Decision
    confidence: float
    reasons: list[str]
    model_score_used: float
    features: dict[str, float | bool]
    source: Literal["computed", "cache"]
    should_create_ops_ticket: bool
    ticket_action: Literal["create", "skip_duplicate", "none"]
    cache_ttl_seconds_remaining: int


class BatchReviewRequest(BaseModel):
    requests: list[ReviewRequest] = Field(min_length=1, max_length=500)


class BatchReviewResponse(BaseModel):
    results: list[ReviewResponse]
    decision_counts: dict[str, int]
    ticket_action_counts: dict[str, int]


def _to_response(request: ReviewRequest, outcome: ReviewOutcome) -> ReviewResponse:
    return ReviewResponse(
        request_id=request.request_id,
        bank_name=request.bank_name,
        pan_name=request.pan_name,
        normalized_bank_name=outcome.features.bank_normalized,
        normalized_pan_name=outcome.features.pan_normalized,
        decision=outcome.decision,
        confidence=outcome.confidence,
        reasons=outcome.reasons,
        model_score_used=round(outcome.model_score_used, 4),
        features=outcome.features.to_dict(),
        source=outcome.source,  # type: ignore[arg-type]
        should_create_ops_ticket=outcome.should_create_ops_ticket,
        ticket_action=outcome.ticket_action,  # type: ignore[arg-type]
        cache_ttl_seconds_remaining=outcome.cache_ttl_seconds_remaining,
    )


def _build_service() -> PartialAcceptReviewService:
    policy_config = PolicyConfig(
        approve_threshold=_env_float("APPROVE_THRESHOLD", 0.86),
        manual_review_floor=_env_float("MANUAL_REVIEW_FLOOR", 0.46),
        reject_threshold=_env_float("REJECT_THRESHOLD", 0.28),
        model_weight=_env_float("MODEL_WEIGHT", 0.35),
    )
    return PartialAcceptReviewService(
        policy_config=policy_config,
        dedupe_ttl_seconds=_env_int("OPS_DEDUPE_TTL_SECONDS", 24 * 60 * 60),
    )


app = FastAPI(
    title="Partial Accept Ops Reducer",
    version="0.1.0",
    description="Second-stage review service that auto-resolves low-risk partial accepts.",
)
_review_service = _build_service()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/partial-accepts/review", response_model=ReviewResponse)
def review_partial_accept(request: ReviewRequest) -> ReviewResponse:
    outcome = _review_service.review(
        bank_name=request.bank_name,
        pan_name=request.pan_name,
        model_score=request.model_score,
    )
    return _to_response(request, outcome)


@app.post("/v1/partial-accepts/review-batch", response_model=BatchReviewResponse)
def review_partial_accept_batch(request: BatchReviewRequest) -> BatchReviewResponse:
    results = [
        _to_response(
            req,
            _review_service.review(
                bank_name=req.bank_name,
                pan_name=req.pan_name,
                model_score=req.model_score,
            ),
        )
        for req in request.requests
    ]
    decision_counts = Counter(result.decision for result in results)
    ticket_action_counts = Counter(result.ticket_action for result in results)
    return BatchReviewResponse(
        results=results,
        decision_counts={decision: count for decision, count in decision_counts.items()},
        ticket_action_counts={action: count for action, count in ticket_action_counts.items()},
    )
