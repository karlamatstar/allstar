from fastapi.testclient import TestClient

from allstar.ai_agent.api.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metrics_endpoint_exposed():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"chat_requests_total" in response.content
