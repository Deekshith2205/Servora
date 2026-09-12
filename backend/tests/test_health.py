from fastapi.testclient import TestClient

from app.agents.classifier import ClassificationResult
from app.agents.planner import PlanDecision
from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_chat_endpoint_runs_end_to_end(monkeypatch):
    # classifier.classify() (issue #3) and planner.plan() (issue #4) both
    # call the real LLM now — mock both so this test stays network-free and
    # runs in CI without an API key. Specialists/verification are still
    # stubs, so no other mocking is needed yet. Any future agent that
    # starts calling the real LLM needs the same treatment here.
    monkeypatch.setattr(
        "app.orchestrator.classify",
        lambda message: ClassificationResult(
            category="order", sentiment="neutral", urgency=3, reasoning="mocked for test"
        ),
    )
    monkeypatch.setattr(
        "app.orchestrator.plan",
        lambda classification, customer_id, db: PlanDecision(
            action="resolve", target_agent="order", reasoning="mocked for test"
        ),
    )

    resp = client.post("/api/chat", json={"customer_id": 1, "message": "Where is my order?"})
    assert resp.status_code == 200
    body = resp.json()
    assert "reply" in body
    assert body["status"] in ("resolved", "escalated")
    assert len(body["trace"]) > 0
