from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum

from name_match_service.config import DecisionConfig
from name_match_service.features import NameFeatures, extract_name_features


class Decision(StrEnum):
    AUTO_ACCEPT = "auto_accept"
    AUTO_REJECT = "auto_reject"
    SEND_TO_OPS = "send_to_ops"


@dataclass(frozen=True)
class DecisionResult:
    decision: Decision
    confidence: float
    reason_codes: list[str]
    features: NameFeatures

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["decision"] = self.decision.value
        return payload


class PartialAcceptTriageEngine:
    def __init__(self, config: DecisionConfig | None = None):
        self.config = config or DecisionConfig.from_env()

    def decide(self, bank_name: str, pan_name: str, ml_score: float | None = None) -> DecisionResult:
        features = extract_name_features(bank_name=bank_name, pan_name=pan_name, ml_score=ml_score)
        reason_codes: list[str] = []

        if features.exact_match:
            reason_codes.append("exact_token_match")
            return DecisionResult(
                decision=Decision.AUTO_ACCEPT,
                confidence=99.0,
                reason_codes=reason_codes,
                features=features,
            )

        if self._is_high_confidence_accept(features):
            reason_codes.extend(self._accept_reasons(features))
            confidence = self._accept_confidence(features)
            return DecisionResult(
                decision=Decision.AUTO_ACCEPT,
                confidence=confidence,
                reason_codes=reason_codes,
                features=features,
            )

        if self._is_high_confidence_reject(features):
            reason_codes.extend(self._reject_reasons(features))
            confidence = self._reject_confidence(features)
            return DecisionResult(
                decision=Decision.AUTO_REJECT,
                confidence=confidence,
                reason_codes=reason_codes,
                features=features,
            )

        reason_codes.append("insufficient_confidence_for_automation")
        if features.first_token_conflict:
            reason_codes.append("first_name_conflict")
        if features.soft_coverage < self.config.auto_accept_min_coverage:
            reason_codes.append("low_token_coverage")

        return DecisionResult(
            decision=Decision.SEND_TO_OPS,
            confidence=self._ops_confidence(features),
            reason_codes=reason_codes,
            features=features,
        )

    def _is_high_confidence_accept(self, features: NameFeatures) -> bool:
        return (
            features.blended_score >= self.config.auto_accept_threshold
            and features.soft_coverage >= self.config.auto_accept_min_coverage
            and not features.first_token_conflict
            and (features.surname_match or features.soft_coverage >= 0.85)
        )

    def _is_high_confidence_reject(self, features: NameFeatures) -> bool:
        too_low_score = features.blended_score <= self.config.auto_reject_threshold
        first_name_conflict = (
            features.first_token_conflict
            and features.blended_score <= self.config.auto_reject_conflict_ceiling
            and features.soft_coverage < 0.80
        )
        poor_coverage = (
            features.soft_coverage <= self.config.hard_reject_min_coverage
            and features.blended_score < self.config.auto_accept_threshold
        )
        return too_low_score or first_name_conflict or poor_coverage

    @staticmethod
    def _accept_confidence(features: NameFeatures) -> float:
        confidence = 55.0 + (0.45 * features.blended_score) + (25.0 * features.soft_coverage)
        if features.first_token_match:
            confidence += 5.0
        if features.surname_match:
            confidence += 5.0
        return round(min(confidence / 2.0, 99.0), 2)

    @staticmethod
    def _reject_confidence(features: NameFeatures) -> float:
        mismatch_strength = max(0.0, 100.0 - features.blended_score)
        confidence = 50.0 + (0.40 * mismatch_strength) + (25.0 * (1.0 - features.soft_coverage))
        if features.first_token_conflict:
            confidence += 6.0
        return round(min(confidence, 99.0), 2)

    @staticmethod
    def _ops_confidence(features: NameFeatures) -> float:
        uncertainty = abs(features.blended_score - 70.0)
        confidence = 45.0 + (uncertainty * 0.15)
        return round(min(confidence, 75.0), 2)

    @staticmethod
    def _accept_reasons(features: NameFeatures) -> list[str]:
        reasons = [
            "high_blended_similarity",
            "adequate_token_coverage",
        ]
        if features.surname_match:
            reasons.append("surname_match")
        if features.first_token_match:
            reasons.append("first_name_match")
        return reasons

    @staticmethod
    def _reject_reasons(features: NameFeatures) -> list[str]:
        reasons: list[str] = []
        if features.blended_score <= 52.0:
            reasons.append("very_low_similarity")
        if features.first_token_conflict:
            reasons.append("first_name_conflict")
        if features.soft_coverage <= 0.35:
            reasons.append("very_low_token_coverage")
        if not reasons:
            reasons.append("high_confidence_mismatch")
        return reasons

