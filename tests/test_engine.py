"""Unit tests for partial accept decision engine."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from partial_accept_service.config import TriageConfig
from partial_accept_service.engine import DecisionEngine
from partial_accept_service.models import Decision, PartialAcceptCase


class DecisionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = DecisionEngine(config=TriageConfig(auto_accept_threshold=0.82, auto_reject_threshold=0.35))

    def test_exact_match_auto_accept(self) -> None:
        case = PartialAcceptCase(
            case_id="1",
            bank_name="Mr Raj Kumar Sharma",
            pan_name="RAJ KUMAR SHARMA",
            ml_score=0.62,
        )
        result = self.engine.triage_case(case)
        self.assertEqual(result.decision, Decision.AUTO_ACCEPT)
        self.assertGreaterEqual(result.decision_score, 0.95)
        self.assertTrue(result.features["exact_match"])

    def test_initials_form_auto_accept(self) -> None:
        case = PartialAcceptCase(
            case_id="2",
            bank_name="R K Sharma",
            pan_name="Raj Kumar Sharma",
            ml_score=0.66,
        )
        result = self.engine.triage_case(case)
        self.assertEqual(result.decision, Decision.AUTO_ACCEPT)
        self.assertTrue(result.features["initials_compatible"])
        self.assertTrue(result.features["surname_match"])

    def test_obvious_mismatch_auto_reject(self) -> None:
        case = PartialAcceptCase(
            case_id="3",
            bank_name="Aman Verma",
            pan_name="Priya Nair",
            ml_score=0.21,
        )
        result = self.engine.triage_case(case)
        self.assertEqual(result.decision, Decision.AUTO_REJECT)
        self.assertLessEqual(result.decision_score, 0.35)

    def test_high_risk_flag_forces_ops_review(self) -> None:
        case = PartialAcceptCase(
            case_id="4",
            bank_name="Rajesh Patel",
            pan_name="Rajesh Patel",
            ml_score=0.98,
            risk_flags=["fraud_watchlist"],
        )
        result = self.engine.triage_case(case)
        self.assertEqual(result.decision, Decision.SEND_TO_OPS)
        self.assertIn("high-risk flag", result.reasons[0])

    def test_ambiguous_case_goes_to_ops(self) -> None:
        case = PartialAcceptCase(
            case_id="5",
            bank_name="Anil Kumar",
            pan_name="Anil K Mishra",
            ml_score=0.71,
        )
        result = self.engine.triage_case(case)
        self.assertEqual(result.decision, Decision.SEND_TO_OPS)

    def test_batch_triage_returns_decisions_for_all_cases(self) -> None:
        cases = [
            PartialAcceptCase(case_id="a", bank_name="R K Sharma", pan_name="Raj Kumar Sharma", ml_score=0.64),
            PartialAcceptCase(case_id="b", bank_name="Aman Verma", pan_name="Priya Nair", ml_score=0.2),
            PartialAcceptCase(case_id="c", bank_name="Anil Kumar", pan_name="Anil K Mishra", ml_score=0.7),
        ]
        results = self.engine.triage_batch(cases)
        self.assertEqual(len(results), 3)
        self.assertEqual([res.case_id for res in results], ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()
