from fastapi.testclient import TestClient
import pytest

from partial_accepts_service.api import create_app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_review_endpoint_returns_ticket_hint(client: TestClient) -> None:
    response = client.post(
        "/v1/partial-accepts/review",
        json={
            "request_id": "req-1",
            "bank_name": "Ravi Kumar Sharma",
            "pan_name": "Ravi Sharma",
            "model_score": 0.73,
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["request_id"] == "req-1"
    assert body["decision"] == "route_to_ops"
    assert body["ticket_action"] == "create"
    assert body["should_create_ops_ticket"] is True
    assert "features" in body


def test_batch_endpoint_counts_actions(client: TestClient) -> None:
    response = client.post(
        "/v1/partial-accepts/review-batch",
        json={
            "requests": [
                {
                    "request_id": "req-a",
                    "bank_name": "Mr. Rakesh Kumar Pvt Ltd.",
                    "pan_name": "Rakesh Kumar",
                    "model_score": 0.65,
                },
                {
                    "request_id": "req-b",
                    "bank_name": "Ravi Kumar Sharma",
                    "pan_name": "Ravi Sharma",
                    "model_score": 0.73,
                },
                {
                    "request_id": "req-c",
                    "bank_name": "Ravi Kumar Sharma",
                    "pan_name": "Ravi Sharma",
                    "model_score": 0.73,
                },
            ]
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["decision_counts"]["auto_approve"] == 1
    assert body["decision_counts"]["route_to_ops"] == 2
    assert body["ticket_action_counts"]["create"] >= 1
    assert body["ticket_action_counts"]["skip_duplicate"] >= 1
