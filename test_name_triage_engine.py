from name_triage_engine import (
    Decision,
    PartialAcceptTriageService,
    TriageInput,
    summarize_results,
)


def test_exact_match_with_noise_auto_accept() -> None:
    service = PartialAcceptTriageService()

    result = service.evaluate(
        TriageInput(
            bank_name="Mr. Rahul Kumar",
            pan_name="RAHUL   KUMAR",
            ml_score=0.62,
        )
    )

    assert result.decision == Decision.AUTO_ACCEPT
    assert "EXACT_NORMALIZED_MATCH" in result.reason_codes


def test_token_order_change_auto_accept() -> None:
    service = PartialAcceptTriageService()

    result = service.evaluate(
        TriageInput(
            bank_name="Singh Rahul",
            pan_name="Rahul Singh",
            ml_score=0.71,
        )
    )

    assert result.decision == Decision.AUTO_ACCEPT
    assert "TOKEN_SET_MATCH" in result.reason_codes


def test_initials_expansion_auto_accept() -> None:
    service = PartialAcceptTriageService()

    result = service.evaluate(
        TriageInput(
            bank_name="Rahul K Singh",
            pan_name="Rahul Kumar Singh",
            ml_score=0.84,
        )
    )

    assert result.decision == Decision.AUTO_ACCEPT
    assert "INITIALS_EXPANSION_MATCH" in result.reason_codes


def test_clear_mismatch_auto_reject() -> None:
    service = PartialAcceptTriageService()

    result = service.evaluate(
        TriageInput(
            bank_name="Amit Gupta",
            pan_name="Priya Menon",
            ml_score=0.30,
        )
    )

    assert result.decision == Decision.AUTO_REJECT


def test_ambiguous_case_goes_to_ops_review() -> None:
    service = PartialAcceptTriageService()

    result = service.evaluate(
        TriageInput(
            bank_name="Rakesh Kumar Sharma",
            pan_name="Rakesh Kumar Verma",
            ml_score=0.76,
        )
    )

    assert result.decision == Decision.NEEDS_OPS_REVIEW
    assert "REQUIRES_HUMAN_REVIEW" in result.reason_codes


def test_summary_includes_ticket_reduction_ratio() -> None:
    service = PartialAcceptTriageService()
    results = [
        service.evaluate(TriageInput(bank_name="Rahul Singh", pan_name="Rahul Singh", ml_score=0.55)),
        service.evaluate(TriageInput(bank_name="Amit Gupta", pan_name="Priya Menon", ml_score=0.25)),
        service.evaluate(
            TriageInput(
                bank_name="Rakesh Kumar Sharma",
                pan_name="Rakesh Kumar Verma",
                ml_score=0.76,
            )
        ),
    ]

    summary = summarize_results(results)

    assert summary["total"] == 3
    assert summary["auto_accept"] == 1
    assert summary["auto_reject"] == 1
    assert summary["needs_ops_review"] == 1
    assert summary["ticket_reduction_ratio"] == 2 / 3
