from app.policy import triage_case, triage_cases
from app.schemas import DecisionType, NameMatchCase, TriagePolicy


DEFAULT_POLICY = TriagePolicy()


def test_auto_approve_exact_name() -> None:
    case = NameMatchCase(
        case_id="c1",
        bank_name="Rahul Kumar Sharma",
        pan_name="RAHUL KUMAR SHARMA",
        model_score=0.70,
    )
    result = triage_case(case, DEFAULT_POLICY)
    assert result.decision == DecisionType.AUTO_APPROVE
    assert result.ops_ticket_required is False


def test_auto_approve_initials_profile() -> None:
    case = NameMatchCase(
        case_id="c2",
        bank_name="R K Sharma",
        pan_name="Rahul Kumar Sharma",
        model_score=0.68,
    )
    result = triage_case(case, DEFAULT_POLICY)
    assert result.decision == DecisionType.AUTO_APPROVE


def test_auto_reject_clear_mismatch() -> None:
    case = NameMatchCase(
        case_id="c3",
        bank_name="Sunita Verma",
        pan_name="Rakesh Gupta",
        model_score=0.22,
    )
    result = triage_case(case, DEFAULT_POLICY)
    assert result.decision == DecisionType.AUTO_REJECT
    assert result.ops_ticket_required is False


def test_review_ops_for_ambiguous_case() -> None:
    case = NameMatchCase(
        case_id="c4",
        bank_name="Anil Kumar",
        pan_name="Anil Kumari",
        model_score=0.63,
    )
    result = triage_case(case, DEFAULT_POLICY)
    assert result.decision == DecisionType.REVIEW_OPS
    assert result.ops_ticket_required is True


def test_batch_summary_counts() -> None:
    response = triage_cases(
        cases=[
            NameMatchCase(
                case_id="c1",
                bank_name="Rahul Kumar Sharma",
                pan_name="Rahul Kumar Sharma",
                model_score=0.75,
            ),
            NameMatchCase(
                case_id="c2",
                bank_name="Sunita Verma",
                pan_name="Rakesh Gupta",
                model_score=0.22,
            ),
            NameMatchCase(
                case_id="c3",
                bank_name="Anil Kumar",
                pan_name="Anil Kumari",
                model_score=0.63,
            ),
        ],
        policy=DEFAULT_POLICY,
    )
    assert response.summary.total_cases == 3
    assert response.summary.auto_approved == 1
    assert response.summary.auto_rejected == 1
    assert response.summary.sent_to_ops == 1
    assert response.summary.ops_reduction_ratio == 0.6667

