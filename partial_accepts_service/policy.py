"""Decision policy to reduce unnecessary ops escalations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from partial_accepts_service.scoring import SimilarityFeatures


class Decision(StrEnum):
    AUTO_APPROVE = "auto_approve"
    ROUTE_TO_OPS = "route_to_ops"
    AUTO_REJECT = "auto_reject"


@dataclass(frozen=True)
class PolicyConfig:
    approve_threshold: float = 0.86
    manual_review_floor: float = 0.46
    reject_threshold: float = 0.28
    model_weight: float = 0.35


@dataclass(frozen=True)
class DecisionResult:
    decision: Decision
    confidence: float
    reasons: list[str]
    model_score_used: float


def _blend_scores(heuristic_score: float, model_score: float | None, model_weight: float) -> tuple[float, float]:
    if model_score is None:
        return heuristic_score, heuristic_score
    blended = (1 - model_weight) * heuristic_score + model_weight * model_score
    return blended, model_score


def apply_policy(
    features: SimilarityFeatures,
    model_score: float | None,
    config: PolicyConfig | None = None,
) -> DecisionResult:
    cfg = config or PolicyConfig()
    blended_score, model_score_used = _blend_scores(features.heuristic_score, model_score, cfg.model_weight)

    reasons: list[str] = []
    if features.bank_normalized == features.pan_normalized and features.bank_normalized:
        reasons.append("exact_normalized_match")
        return DecisionResult(
            decision=Decision.AUTO_APPROVE,
            confidence=1.0,
            reasons=reasons,
            model_score_used=model_score_used,
        )

    if features.abbreviation_match and features.last_token_match:
        reasons.append("abbreviation_consistent")
        if blended_score >= (cfg.approve_threshold - 0.08):
            reasons.append("high_confidence_after_abbreviation_relaxation")
            return DecisionResult(
                decision=Decision.AUTO_APPROVE,
                confidence=round(blended_score, 4),
                reasons=reasons,
                model_score_used=model_score_used,
            )

    if blended_score >= cfg.approve_threshold:
        reasons.append("above_auto_approve_threshold")
        return DecisionResult(
            decision=Decision.AUTO_APPROVE,
            confidence=round(blended_score, 4),
            reasons=reasons,
            model_score_used=model_score_used,
        )

    if (
        blended_score <= cfg.reject_threshold
        and features.token_jaccard <= 0.15
        and features.sequence_ratio <= 0.45
    ):
        reasons.append("strong_mismatch_signals")
        return DecisionResult(
            decision=Decision.AUTO_REJECT,
            confidence=round(1 - blended_score, 4),
            reasons=reasons,
            model_score_used=model_score_used,
        )

    if blended_score < cfg.manual_review_floor and not features.last_token_match:
        reasons.append("low_similarity_without_last_name_match")
        return DecisionResult(
            decision=Decision.AUTO_REJECT,
            confidence=round(1 - blended_score, 4),
            reasons=reasons,
            model_score_used=model_score_used,
        )

    reasons.append("borderline_case_route_to_ops")
    return DecisionResult(
        decision=Decision.ROUTE_TO_OPS,
        confidence=round(blended_score, 4),
        reasons=reasons,
        model_score_used=model_score_used,
    )
