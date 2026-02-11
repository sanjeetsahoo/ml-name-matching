from __future__ import annotations

from app.scoring import extract_similarity_features
from app.schemas import (
    CaseDecision,
    DecisionType,
    NameMatchCase,
    TriagePolicy,
    TriageResponse,
    TriageSummary,
)


def _validate_policy(policy: TriagePolicy) -> None:
    if policy.auto_reject_threshold >= policy.auto_approve_threshold:
        raise ValueError("auto_reject_threshold must be lower than auto_approve_threshold")
    if policy.low_model_score_threshold >= policy.high_model_score_threshold:
        raise ValueError("low_model_score_threshold must be lower than high_model_score_threshold")


def _approve_guardrail(case: NameMatchCase, surname_mismatch: bool) -> bool:
    # Block auto-approval if core identity token seems contradictory.
    return not (surname_mismatch and case.model_score < 0.90)


def _decision_confidence(
    decision: DecisionType,
    combined_score: float,
    policy: TriagePolicy,
) -> float:
    if decision == DecisionType.AUTO_APPROVE:
        band = 1.0 - policy.auto_approve_threshold
        return min(1.0, 0.5 + ((combined_score - policy.auto_approve_threshold) / band if band > 0 else 0.5))
    if decision == DecisionType.AUTO_REJECT:
        band = policy.auto_reject_threshold
        return min(1.0, 0.5 + ((policy.auto_reject_threshold - combined_score) / band if band > 0 else 0.5))
    midpoint = (policy.auto_approve_threshold + policy.auto_reject_threshold) / 2
    distance = abs(combined_score - midpoint)
    return max(0.3, 0.8 - distance)


def triage_case(case: NameMatchCase, policy: TriagePolicy, include_features: bool = True) -> CaseDecision:
    _validate_policy(policy)
    features = extract_similarity_features(case.bank_name, case.pan_name, case.model_score)

    surname_mismatch = "surname_mismatch" in features.risk_flags
    low_overlap = "low_token_overlap" in features.risk_flags

    approve_condition = (
        features.combined_score >= policy.auto_approve_threshold
        and _approve_guardrail(case, surname_mismatch)
        and (
            case.model_score >= policy.high_model_score_threshold
            or features.token_overlap_shorter >= 0.95
            or (features.surname_match and features.initial_alignment >= 0.90)
        )
    )

    reject_condition = (
        features.combined_score <= policy.auto_reject_threshold
        and case.model_score <= policy.low_model_score_threshold
    ) or (surname_mismatch and low_overlap and features.combined_score < 0.70)

    reasons: list[str] = []
    if approve_condition:
        decision = DecisionType.AUTO_APPROVE
        reasons.append("High composite similarity with strong token alignment.")
        if features.subset_match:
            reasons.append("One name is structurally contained in the other (likely abbreviation/initials).")
    elif reject_condition:
        decision = DecisionType.AUTO_REJECT
        reasons.append("Low composite similarity and weak overlap indicate mismatch.")
        if surname_mismatch:
            reasons.append("Surname mismatch detected under low-overlap profile.")
    else:
        decision = DecisionType.REVIEW_OPS
        reasons.append("Ambiguous case retained for manual review.")
        if features.risk_flags:
            reasons.append(f"Risk flags: {', '.join(features.risk_flags)}")

    confidence = _decision_confidence(decision, features.combined_score, policy)

    return CaseDecision(
        case_id=case.case_id,
        decision=decision,
        confidence=round(confidence, 4),
        ops_ticket_required=decision == DecisionType.REVIEW_OPS,
        reasons=reasons,
        features=features if include_features else None,
        metadata=case.metadata,
    )


def triage_cases(
    cases: list[NameMatchCase],
    policy: TriagePolicy,
    include_features: bool = True,
) -> TriageResponse:
    _validate_policy(policy)
    decisions = [triage_case(case, policy, include_features=include_features) for case in cases]

    auto_approved = sum(1 for d in decisions if d.decision == DecisionType.AUTO_APPROVE)
    auto_rejected = sum(1 for d in decisions if d.decision == DecisionType.AUTO_REJECT)
    sent_to_ops = sum(1 for d in decisions if d.decision == DecisionType.REVIEW_OPS)
    total_cases = len(decisions)

    summary = TriageSummary(
        total_cases=total_cases,
        auto_approved=auto_approved,
        auto_rejected=auto_rejected,
        sent_to_ops=sent_to_ops,
        ops_reduction_ratio=round((auto_approved + auto_rejected) / total_cases if total_cases else 0.0, 4),
    )
    return TriageResponse(summary=summary, decisions=decisions)

