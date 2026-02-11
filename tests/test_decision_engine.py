from name_match_service.decision_engine import Decision, PartialAcceptTriageEngine


def test_exact_name_match_auto_accepts() -> None:
    engine = PartialAcceptTriageEngine()
    result = engine.decide(
        bank_name="Rakesh Kumar Sharma",
        pan_name="Rakesh Kumar Sharma",
        ml_score=0.62,
    )
    assert result.decision == Decision.AUTO_ACCEPT
    assert "exact_token_match" in result.reason_codes


def test_clear_name_mismatch_auto_rejects() -> None:
    engine = PartialAcceptTriageEngine()
    result = engine.decide(
        bank_name="Priya Gupta",
        pan_name="Mohit Sharma",
        ml_score=0.12,
    )
    assert result.decision == Decision.AUTO_REJECT
    assert result.confidence >= 75


def test_partial_name_ambiguity_goes_to_ops() -> None:
    engine = PartialAcceptTriageEngine()
    result = engine.decide(
        bank_name="Anil Singh",
        pan_name="Anil Kumar Singh",
        ml_score=0.70,
    )
    assert result.decision == Decision.SEND_TO_OPS
    assert "insufficient_confidence_for_automation" in result.reason_codes

