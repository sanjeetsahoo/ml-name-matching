from partial_accept_service.config import DecisionSettings
from partial_accept_service.features import NameMatchFeatures, calculate_name_match_features
from partial_accept_service.schemas import (
    DecisionAction,
    DecisionResponse,
    FeatureSummary,
    PartialAcceptCase,
)


def _clip_01(value: float) -> float:
    return max(0.0, min(1.0, value))


class PartialAcceptDecisionEngine:
    def __init__(self, settings: DecisionSettings | None = None) -> None:
        self.settings = settings or DecisionSettings()

    def _automation_score(self, ml_score: float, features: NameMatchFeatures) -> float:
        score = (
            self.settings.model_weight * ml_score
            + self.settings.token_sort_weight * (features.token_sort_similarity / 100.0)
            + self.settings.jaccard_weight * features.token_jaccard
            + self.settings.containment_weight * features.token_containment
        )

        if features.initials_compatible:
            score += self.settings.initials_bonus
        if features.normalized_equal:
            score += self.settings.exact_bonus
        if features.first_token_conflict:
            score -= 0.05
        if features.hard_mismatch:
            score -= self.settings.hard_mismatch_penalty

        return _clip_01(score)

    def decide(self, case: PartialAcceptCase) -> DecisionResponse:
        features = calculate_name_match_features(case.bank_name, case.pan_name)
        decision_score = round(self._automation_score(case.ml_score, features), 4)

        reasons: list[str] = []
        if features.normalized_equal:
            reasons.append("Names are identical after normalization.")
        if features.initials_compatible:
            reasons.append("Initials pattern is compatible across names.")
        if features.first_token_conflict:
            reasons.append("Primary name token appears conflicting.")
        if features.hard_mismatch:
            reasons.append("Hard mismatch guardrail triggered.")

        action = DecisionAction.SEND_TO_OPS

        if features.hard_mismatch:
            if (
                case.ml_score <= self.settings.max_ml_score_for_auto_reject
                and decision_score <= (self.settings.auto_reject_threshold + 0.10)
            ):
                action = DecisionAction.AUTO_REJECT
                reasons.append("Low confidence with guardrail mismatch, auto-rejected.")
            else:
                action = DecisionAction.SEND_TO_OPS
                reasons.append("Conflicting signals despite model confidence, sending to Ops.")
        elif decision_score >= self.settings.auto_accept_threshold:
            action = DecisionAction.AUTO_ACCEPT
            reasons.append("High aggregate confidence, auto-accepted.")
        elif (
            decision_score <= self.settings.auto_reject_threshold
            and case.ml_score <= self.settings.max_ml_score_for_auto_reject
        ):
            action = DecisionAction.AUTO_REJECT
            reasons.append("Low aggregate confidence, auto-rejected.")
        elif (
            case.ml_score >= self.settings.strong_model_accept_threshold
            and features.token_jaccard >= 0.5
            and not features.first_token_conflict
        ):
            action = DecisionAction.AUTO_ACCEPT
            reasons.append("Strong model score with healthy token overlap.")
        else:
            action = DecisionAction.SEND_TO_OPS
            reasons.append("Decision score in gray zone, keeping human review.")

        return DecisionResponse(
            case_id=case.case_id,
            action=action,
            decision_score=decision_score,
            ops_ticket_required=action == DecisionAction.SEND_TO_OPS,
            reasons=reasons,
            features=FeatureSummary(**features.asdict()),
        )
