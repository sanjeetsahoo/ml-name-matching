from partial_accept_service.decision_engine import PartialAcceptDecisionEngine
from partial_accept_service.schemas import DecisionAction, PartialAcceptCase


def _decide(bank_name: str, pan_name: str, ml_score: float) -> DecisionAction:
    engine = PartialAcceptDecisionEngine()
    result = engine.decide(
        PartialAcceptCase(
            case_id="t-1",
            bank_name=bank_name,
            pan_name=pan_name,
            ml_score=ml_score,
        )
    )
    return result.action


def test_exact_match_is_auto_accepted() -> None:
    action = _decide("Mr. Rahul Kumar", "RAHUL KUMAR", 0.72)
    assert action == DecisionAction.AUTO_ACCEPT


def test_confident_overlap_can_auto_accept() -> None:
    action = _decide("SACHIN R TENDULKAR", "SACHIN TENDULKAR", 0.94)
    assert action == DecisionAction.AUTO_ACCEPT


def test_low_confidence_hard_mismatch_is_auto_rejected() -> None:
    action = _decide("AMIT KUMAR", "SUNITA VERMA", 0.20)
    assert action == DecisionAction.AUTO_REJECT


def test_hard_mismatch_with_high_ml_score_goes_to_ops() -> None:
    action = _decide("RAHUL SHARMA", "PRIYA GUPTA", 0.80)
    assert action == DecisionAction.SEND_TO_OPS


def test_ambiguous_case_goes_to_ops() -> None:
    action = _decide("ANIL KUMAR", "ANIL KUMARI", 0.62)
    assert action == DecisionAction.SEND_TO_OPS
