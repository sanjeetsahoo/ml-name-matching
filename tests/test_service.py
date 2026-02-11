from partial_accepts_service.policy import Decision
from partial_accepts_service.service import PartialAcceptReviewService


def test_exact_match_after_normalization_auto_approves() -> None:
    service = PartialAcceptReviewService()
    outcome = service.review(
        bank_name="Mr. Rakesh Kumar Pvt Ltd.",
        pan_name="Rakesh Kumar",
        model_score=0.51,
    )

    assert outcome.decision == Decision.AUTO_APPROVE
    assert "exact_normalized_match" in outcome.reasons
    assert outcome.should_create_ops_ticket is False


def test_borderline_case_routes_to_ops() -> None:
    service = PartialAcceptReviewService()
    outcome = service.review(
        bank_name="Ravi Kumar Sharma",
        pan_name="Ravi Sharma",
        model_score=0.73,
    )

    assert outcome.decision == Decision.ROUTE_TO_OPS
    assert outcome.should_create_ops_ticket is True
    assert outcome.ticket_action == "create"


def test_clear_mismatch_auto_rejects() -> None:
    service = PartialAcceptReviewService()
    outcome = service.review(
        bank_name="Pooja Gupta",
        pan_name="Ravi Sharma",
        model_score=0.21,
    )

    assert outcome.decision == Decision.AUTO_REJECT
    assert outcome.should_create_ops_ticket is False


def test_duplicate_ops_case_skips_second_ticket() -> None:
    service = PartialAcceptReviewService(dedupe_ttl_seconds=3600)
    first = service.review(
        bank_name="Ravi Kumar Sharma",
        pan_name="Ravi Sharma",
        model_score=0.73,
    )
    second = service.review(
        bank_name="Ravi Kumar Sharma",
        pan_name="Ravi Sharma",
        model_score=0.73,
    )

    assert first.decision == Decision.ROUTE_TO_OPS
    assert first.ticket_action == "create"
    assert second.decision == Decision.ROUTE_TO_OPS
    assert second.source == "cache"
    assert second.ticket_action == "skip_duplicate"
    assert second.should_create_ops_ticket is False
