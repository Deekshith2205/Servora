from fastapi.testclient import TestClient

from app.agents.classifier import ClassificationResult
from app.agents.planner import PlanDecision
from app.agents.specialists import SpecialistResponse
from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_chat_endpoint_runs_end_to_end(monkeypatch):
    # classifier.classify() (#3), planner.plan() (#4), every specialist
    # (#6-#9), and now the memory-write step (#11) all call the real LLM —
    # mock all of them so this test stays network-free and runs in CI
    # without an API key. Verification (still a stub, auto-approves) is the
    # only remaining unmocked agent. Any future agent that starts calling
    # the real LLM needs the same treatment here.
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
    mocked_specialist = lambda db, customer_id, message: SpecialistResponse(
        reply="mocked specialist reply", used_tools=[], confidence=0.9
    )
    monkeypatch.setattr(
        "app.orchestrator.SPECIALISTS",
        {"order": mocked_specialist, "technical": mocked_specialist},
    )
    monkeypatch.setattr("app.orchestrator.extract_facts", lambda message, reply: [])

    resp = client.post("/api/chat", json={"customer_id": 1, "message": "Where is my order?"})
    assert resp.status_code == 200
    body = resp.json()
    assert "reply" in body
    assert body["status"] in ("resolved", "escalated")
    assert len(body["trace"]) > 0
