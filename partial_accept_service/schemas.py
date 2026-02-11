from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DecisionAction(str, Enum):
    AUTO_ACCEPT = "AUTO_ACCEPT"
    AUTO_REJECT = "AUTO_REJECT"
    SEND_TO_OPS = "SEND_TO_OPS"


class PartialAcceptCase(BaseModel):
    case_id: str | None = None
    bank_name: str = Field(min_length=1)
    pan_name: str = Field(min_length=1)
    ml_score: float = Field(ge=0.0, le=1.0)
    model_version: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class FeatureSummary(BaseModel):
    normalized_bank_name: str
    normalized_pan_name: str
    normalized_equal: bool
    token_jaccard: float
    token_containment: float
    raw_similarity: float
    token_sort_similarity: float
    initials_compatible: bool
    first_token_conflict: bool
    hard_mismatch: bool


class DecisionResponse(BaseModel):
    case_id: str | None = None
    action: DecisionAction
    decision_score: float = Field(ge=0.0, le=1.0)
    ops_ticket_required: bool
    reasons: list[str]
    features: FeatureSummary


class BatchDecisionRequest(BaseModel):
    cases: list[PartialAcceptCase] = Field(min_length=1)


class BatchDecisionResponse(BaseModel):
    decisions: list[DecisionResponse]
