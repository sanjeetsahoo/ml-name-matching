from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Decision(str, Enum):
    auto_accept = "auto_accept"
    send_to_ops = "send_to_ops"
    auto_reject = "auto_reject"


EntityType = Literal["individual", "company", "unknown"]


class ResolveRequest(BaseModel):
    bank_name: str = Field(..., min_length=1)
    pan_name: str = Field(..., min_length=1)

    # Optional: score from the upstream ML model (0..1). If absent, we rely on rules only.
    ml_score: float | None = Field(default=None, ge=0.0, le=1.0)

    # Optional: useful for tracing / audit
    request_id: str | None = None
    entity_type: EntityType = "unknown"
    metadata: dict[str, Any] | None = None


class ResolveResponse(BaseModel):
    decision: Decision
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasons: list[str]

    bank_normalized: str
    pan_normalized: str

    # Debug features to help tune thresholds / rules
    features: dict[str, Any]
