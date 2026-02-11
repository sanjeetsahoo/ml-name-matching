"""Typed models for the partial accept triage service."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Decision(str, Enum):
    """Decision labels returned by the secondary triage service."""

    AUTO_ACCEPT = "AUTO_ACCEPT"
    AUTO_REJECT = "AUTO_REJECT"
    SEND_TO_OPS = "SEND_TO_OPS"


@dataclass(frozen=True)
class PartialAcceptCase:
    """Input payload for one partial-accept case."""

    bank_name: str
    pan_name: str
    ml_score: float
    case_id: str | None = None
    risk_flags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PartialAcceptCase":
        """Build and validate a case from an untyped request payload."""
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")

        bank_name = payload.get("bank_name", "")
        pan_name = payload.get("pan_name", "")
        ml_score = payload.get("ml_score")

        if not isinstance(bank_name, str) or not bank_name.strip():
            raise ValueError("bank_name must be a non-empty string")
        if not isinstance(pan_name, str) or not pan_name.strip():
            raise ValueError("pan_name must be a non-empty string")
        if not isinstance(ml_score, (float, int)):
            raise ValueError("ml_score must be a number between 0 and 1")

        normalized_ml_score = float(ml_score)
        if normalized_ml_score < 0.0 or normalized_ml_score > 1.0:
            raise ValueError("ml_score must be between 0 and 1")

        case_id = payload.get("case_id")
        if case_id is not None and not isinstance(case_id, str):
            raise ValueError("case_id must be a string when provided")

        risk_flags = payload.get("risk_flags", [])
        if risk_flags is None:
            risk_flags = []
        if not isinstance(risk_flags, list) or any(
            not isinstance(flag, str) for flag in risk_flags
        ):
            raise ValueError("risk_flags must be a list of strings")

        metadata = payload.get("metadata", {})
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be an object when provided")

        return cls(
            bank_name=bank_name,
            pan_name=pan_name,
            ml_score=normalized_ml_score,
            case_id=case_id,
            risk_flags=risk_flags,
            metadata=metadata,
        )


@dataclass(frozen=True)
class DecisionResult:
    """Engine output for one partial-accept case."""

    case_id: str | None
    decision: Decision
    decision_score: float
    reasons: list[str]
    features: dict[str, float | bool | str]

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable response structure."""
        return {
            "case_id": self.case_id,
            "decision": self.decision.value,
            "decision_score": round(self.decision_score, 4),
            "should_create_ops_ticket": self.decision == Decision.SEND_TO_OPS,
            "reasons": self.reasons,
            "features": self.features,
        }
