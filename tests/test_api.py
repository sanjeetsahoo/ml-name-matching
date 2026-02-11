"""Integration-like tests for HTTP API routes."""

from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from partial_accept_service.api import create_server
from partial_accept_service.config import TriageConfig
from partial_accept_service.engine import DecisionEngine


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        config = TriageConfig(auto_accept_threshold=0.82, auto_reject_threshold=0.35)
        engine = DecisionEngine(config=config)
        self.server = create_server("127.0.0.1", 0, decision_engine=engine)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def _post_json(self, path: str, payload: object) -> dict:
        request = urllib.request.Request(
            url=f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_health_endpoint(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/health", timeout=3) as response:
            body = json.loads(response.read().decode("utf-8"))
        self.assertEqual(body, {"status": "ok"})

    def test_triage_endpoint(self) -> None:
        body = self._post_json(
            "/triage",
            {
                "case_id": "case-1",
                "bank_name": "R K Sharma",
                "pan_name": "Raj Kumar Sharma",
                "ml_score": 0.66,
            },
        )
        self.assertEqual(body["case_id"], "case-1")
        self.assertEqual(body["decision"], "AUTO_ACCEPT")
        self.assertIn("reasons", body)

    def test_triage_batch_endpoint(self) -> None:
        body = self._post_json(
            "/triage/batch",
            {
                "cases": [
                    {
                        "case_id": "accept-1",
                        "bank_name": "R K Sharma",
                        "pan_name": "Raj Kumar Sharma",
                        "ml_score": 0.66,
                    },
                    {
                        "case_id": "reject-1",
                        "bank_name": "Aman Verma",
                        "pan_name": "Priya Nair",
                        "ml_score": 0.2,
                    },
                ]
            },
        )
        self.assertEqual(body["total_cases"], 2)
        self.assertEqual(body["decision_counts"]["AUTO_ACCEPT"], 1)
        self.assertEqual(body["decision_counts"]["AUTO_REJECT"], 1)


if __name__ == "__main__":
    unittest.main()
