from fastapi.testclient import TestClient

from name_match_service.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_single_decision_endpoint() -> None:
    payload = {
        "request_id": "case-1",
        "bank_name": "Rakesh Kumar Sharma",
        "pan_name": "Rakesh Kumar Sharma",
        "ml_score": 0.55,
    }
    response = client.post("/v1/partial-accepts/decision", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "case-1"
    assert body["decision"] == "auto_accept"
    assert body["ops_ticket_required"] is False


def test_batch_decision_endpoint_returns_summary_counts() -> None:
    payload = {
        "items": [
            {
                "request_id": "case-accept",
                "bank_name": "Rakesh Kumar Sharma",
                "pan_name": "Rakesh Kumar Sharma",
                "ml_score": 0.9,
            },
            {
                "request_id": "case-reject",
                "bank_name": "Priya Gupta",
                "pan_name": "Mohit Sharma",
                "ml_score": 0.1,
            },
            {
                "request_id": "case-ops",
                "bank_name": "Anil Singh",
                "pan_name": "Anil Kumar Singh",
                "ml_score": 0.7,
            },
        ]
    }

    response = client.post("/v1/partial-accepts/decision/batch", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["total_items"] == 3
    assert body["auto_accept_count"] == 1
    assert body["auto_reject_count"] == 1
    assert body["sent_to_ops_count"] == 1
    assert len(body["decisions"]) == 3

