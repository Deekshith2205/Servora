from fastapi.testclient import TestClient

from app.agents.classifier import ClassificationResult
from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_chat_endpoint_runs_end_to_end(monkeypatch):
    # classifier.classify() now calls the real LLM (issue #3) — mock it so
    # this test stays network-free and runs in CI without an API key.
    # Downstream agents (planner, specialists, verification) are still
    # stubs, so no other mocking is needed yet.
    monkeypatch.setattr(
        "app.orchestrator.classify",
        lambda message: ClassificationResult(
            category="order", sentiment="neutral", urgency=3, reasoning="mocked for test"
        ),
    )

    resp = client.post("/api/chat", json={"customer_id": 1, "message": "Where is my order?"})
    assert resp.status_code == 200
    body = resp.json()
    assert "reply" in body
    assert body["status"] in ("resolved", "escalated")
    assert len(body["trace"]) > 0
