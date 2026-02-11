"""Core service that re-evaluates partial accepts before ops routing."""

from __future__ import annotations

from dataclasses import dataclass, replace

from partial_accepts_service.cache import TtlCache
from partial_accepts_service.normalization import normalize_name
from partial_accepts_service.policy import Decision, DecisionResult, PolicyConfig, apply_policy
from partial_accepts_service.scoring import SimilarityFeatures, build_similarity_features


@dataclass(frozen=True)
class ReviewOutcome:
    decision: Decision
    confidence: float
    reasons: list[str]
    model_score_used: float
    features: SimilarityFeatures
    source: str
    should_create_ops_ticket: bool
    ticket_action: str
    cache_ttl_seconds_remaining: int = 0


class PartialAcceptReviewService:
    def __init__(
        self,
        policy_config: PolicyConfig | None = None,
        dedupe_ttl_seconds: int = 24 * 60 * 60,
    ) -> None:
        self._policy_config = policy_config or PolicyConfig()
        self._dedupe_cache: TtlCache[ReviewOutcome] = TtlCache(ttl_seconds=dedupe_ttl_seconds)

    @staticmethod
    def _build_cache_key(bank_name: str, pan_name: str) -> str:
        return f"{normalize_name(bank_name)}||{normalize_name(pan_name)}"

    def _from_decision(self, decision_result: DecisionResult, features: SimilarityFeatures) -> ReviewOutcome:
        should_create_ops_ticket = decision_result.decision == Decision.ROUTE_TO_OPS
        return ReviewOutcome(
            decision=decision_result.decision,
            confidence=decision_result.confidence,
            reasons=decision_result.reasons,
            model_score_used=decision_result.model_score_used,
            features=features,
            source="computed",
            should_create_ops_ticket=should_create_ops_ticket,
            ticket_action="create" if should_create_ops_ticket else "none",
        )

    def review(self, bank_name: str, pan_name: str, model_score: float | None = None) -> ReviewOutcome:
        if model_score is not None and not 0 <= model_score <= 1:
            raise ValueError("model_score must be between 0 and 1")

        cache_key = self._build_cache_key(bank_name, pan_name)
        cached_outcome, ttl_remaining = self._dedupe_cache.get(cache_key)
        if cached_outcome is not None:
            reasons = list(cached_outcome.reasons)
            if cached_outcome.decision == Decision.ROUTE_TO_OPS:
                reasons.append("duplicate_pair_recently_escalated")
                return replace(
                    cached_outcome,
                    reasons=reasons,
                    source="cache",
                    should_create_ops_ticket=False,
                    ticket_action="skip_duplicate",
                    cache_ttl_seconds_remaining=ttl_remaining,
                )
            return replace(
                cached_outcome,
                reasons=reasons,
                source="cache",
                ticket_action="none",
                cache_ttl_seconds_remaining=ttl_remaining,
            )

        features = build_similarity_features(bank_name=bank_name, pan_name=pan_name)
        if not features.bank_tokens or not features.pan_tokens:
            outcome = ReviewOutcome(
                decision=Decision.AUTO_REJECT,
                confidence=1.0,
                reasons=["empty_or_invalid_name_after_normalization"],
                model_score_used=model_score if model_score is not None else 0.0,
                features=features,
                source="computed",
                should_create_ops_ticket=False,
                ticket_action="none",
            )
            self._dedupe_cache.set(cache_key, outcome)
            return outcome

        decision_result = apply_policy(
            features=features,
            model_score=model_score,
            config=self._policy_config,
        )
        outcome = self._from_decision(decision_result=decision_result, features=features)
        self._dedupe_cache.set(cache_key, outcome)
        return outcome
