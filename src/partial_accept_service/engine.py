"""Decision engine that triages partial-accept name matches."""

from __future__ import annotations

from dataclasses import dataclass

from .config import TriageConfig
from .models import Decision, DecisionResult, PartialAcceptCase
from .normalization import (
    initials_compatible,
    normalize_name,
    sequence_similarity,
    surnames_match,
    token_coverage,
    token_jaccard,
)

HIGH_RISK_FLAGS = {
    "fraud_watchlist",
    "sanctions_hit",
    "pep_hit",
    "manual_review_required",
}


@dataclass(frozen=True)
class FeatureBundle:
    bank_normalized: str
    pan_normalized: str
    bank_tokens: tuple[str, ...]
    pan_tokens: tuple[str, ...]
    sequence_score: float
    jaccard_score: float
    pan_coverage: float
    bank_coverage: float
    initials_match: bool
    surname_match: bool
    exact_match: bool


class DecisionEngine:
    """Secondary triage engine to reduce avoidable ops tickets."""

    def __init__(self, config: TriageConfig | None = None) -> None:
        self.config = config or TriageConfig.from_env()

    def triage_case(self, case: PartialAcceptCase) -> DecisionResult:
        features = self._extract_features(case)
        composite_score = self._composite_score(case.ml_score, features)
        reasons: list[str] = []

        if not features.bank_tokens or not features.pan_tokens:
            reasons.append("name normalization removed too many informative tokens")
            return self._result(case, Decision.SEND_TO_OPS, composite_score, reasons, features)

        lowered_flags = {flag.strip().lower() for flag in case.risk_flags}
        if lowered_flags & HIGH_RISK_FLAGS:
            reasons.append("high-risk flag present; forcing manual ops verification")
            return self._result(case, Decision.SEND_TO_OPS, composite_score, reasons, features)

        if features.exact_match:
            reasons.append("normalized names match exactly")
            return self._result(case, Decision.AUTO_ACCEPT, max(0.99, composite_score), reasons, features)

        if (
            features.surname_match
            and features.sequence_score >= 0.94
            and features.jaccard_score >= 0.80
        ):
            reasons.append("high lexical match with stable surname")
            return self._result(case, Decision.AUTO_ACCEPT, max(0.95, composite_score), reasons, features)

        if (
            features.surname_match
            and features.initials_match
            and features.pan_coverage >= 0.75
            and case.ml_score >= 0.58
        ):
            reasons.append("initial-based abbreviation is consistent with PAN name")
            return self._result(case, Decision.AUTO_ACCEPT, max(0.88, composite_score), reasons, features)

        if (
            not features.surname_match
            and features.jaccard_score <= 0.15
            and features.sequence_score <= 0.45
            and case.ml_score <= 0.45
        ):
            reasons.append("strong mismatch across model and token-level signals")
            return self._result(case, Decision.AUTO_REJECT, min(0.2, composite_score), reasons, features)

        if features.pan_coverage == 0.0 and case.ml_score <= 0.35:
            reasons.append("none of PAN tokens appear in bank name")
            return self._result(case, Decision.AUTO_REJECT, min(0.25, composite_score), reasons, features)

        if composite_score >= self.config.auto_accept_threshold and features.surname_match:
            reasons.append("composite confidence crossed auto-accept threshold")
            return self._result(case, Decision.AUTO_ACCEPT, composite_score, reasons, features)

        if composite_score <= self.config.auto_reject_threshold and not features.initials_match:
            reasons.append("composite confidence below auto-reject threshold")
            return self._result(case, Decision.AUTO_REJECT, composite_score, reasons, features)

        reasons.append("ambiguous match; keep manual ops review")
        return self._result(case, Decision.SEND_TO_OPS, composite_score, reasons, features)

    def triage_batch(self, cases: list[PartialAcceptCase]) -> list[DecisionResult]:
        return [self.triage_case(case) for case in cases]

    def _extract_features(self, case: PartialAcceptCase) -> FeatureBundle:
        bank_normalized = normalize_name(case.bank_name)
        pan_normalized = normalize_name(case.pan_name)
        bank_tokens = tuple(bank_normalized.split()) if bank_normalized else tuple()
        pan_tokens = tuple(pan_normalized.split()) if pan_normalized else tuple()

        seq_score = sequence_similarity(bank_normalized, pan_normalized)
        jaccard_score = token_jaccard(bank_tokens, pan_tokens)
        pan_cov = token_coverage(pan_tokens, bank_tokens)
        bank_cov = token_coverage(bank_tokens, pan_tokens)
        initials_match = initials_compatible(bank_tokens, pan_tokens)
        surname_match = surnames_match(bank_tokens, pan_tokens)
        exact_match = bank_normalized == pan_normalized and bool(bank_normalized)

        return FeatureBundle(
            bank_normalized=bank_normalized,
            pan_normalized=pan_normalized,
            bank_tokens=bank_tokens,
            pan_tokens=pan_tokens,
            sequence_score=seq_score,
            jaccard_score=jaccard_score,
            pan_coverage=pan_cov,
            bank_coverage=bank_cov,
            initials_match=initials_match,
            surname_match=surname_match,
            exact_match=exact_match,
        )

    @staticmethod
    def _composite_score(ml_score: float, features: FeatureBundle) -> float:
        score = (
            0.45 * ml_score
            + 0.25 * features.sequence_score
            + 0.20 * features.jaccard_score
            + 0.10 * features.pan_coverage
        )

        if features.initials_match:
            score += 0.03
        if features.surname_match:
            score += 0.05
        else:
            score -= 0.07
        if features.exact_match:
            score += 0.15

        return max(0.0, min(1.0, score))

    @staticmethod
    def _result(
        case: PartialAcceptCase,
        decision: Decision,
        score: float,
        reasons: list[str],
        features: FeatureBundle,
    ) -> DecisionResult:
        return DecisionResult(
            case_id=case.case_id,
            decision=decision,
            decision_score=max(0.0, min(1.0, score)),
            reasons=reasons,
            features={
                "bank_name_normalized": features.bank_normalized,
                "pan_name_normalized": features.pan_normalized,
                "ml_score": round(case.ml_score, 4),
                "sequence_similarity": round(features.sequence_score, 4),
                "token_jaccard": round(features.jaccard_score, 4),
                "pan_token_coverage": round(features.pan_coverage, 4),
                "bank_token_coverage": round(features.bank_coverage, 4),
                "initials_compatible": features.initials_match,
                "surname_match": features.surname_match,
                "exact_match": features.exact_match,
            },
        )
