"""Tests for GET /api/escalations/{id} (issue #14).

Uses the real app + real (seeded) demo DB via TestClient, same as
test_health.py — the seeded tickets never went through the pipeline, so
they're the natural case for "trace/handoff_packet is None".
"""
from fastapi.testclient import TestClient

from app.agents.classifier import ClassificationResult
from app.agents.escalation import HandoffPacket
from app.agents.planner import PlanDecision
from app.main import app

client = TestClient(app)


def test_escalation_detail_404_for_missing_ticket():
    resp = client.get("/api/escalations/999999")
    assert resp.status_code == 404


def test_escalation_detail_for_a_seeded_ticket_has_no_trace_or_packet():
    # Seeded tickets (db/seed.py) never went through /api/chat.
    seeded = client.get("/api/escalations").json()
    assert len(seeded) > 0
    ticket_id = seeded[0]["id"]

    resp = client.get(f"/api/escalations/{ticket_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["trace"] is None
    assert body["handoff_packet"] is None


def test_escalation_detail_for_a_real_escalation_has_trace_and_packet(monkeypatch):
    monkeypatch.setattr(
        "app.orchestrator.classify",
        lambda message: ClassificationResult(
            category="account", sentiment="neutral", urgency=8, reasoning="mocked for test"
        ),
    )
    monkeypatch.setattr(
        "app.orchestrator.plan",
        lambda classification, customer_id, db: PlanDecision(
            action="escalate", target_agent="none", reasoning="mocked escalate"
        ),
    )
    monkeypatch.setattr(
        "app.orchestrator.build_handoff_packet",
        lambda message, attempted_fixes, urgency, confidence=None: HandoffPacket(
            situation="test situation",
            attempted_fixes=attempted_fixes,
            root_cause_hypothesis="test root cause",
            recommended_action="test action",
            urgency=urgency,
        ),
    )

    chat_resp = client.post("/api/chat", json={"customer_id": 1, "message": "please grant a policy exception"})
    assert chat_resp.status_code == 200

    escalations = client.get("/api/escalations").json()
    newest = max(escalations, key=lambda t: t["id"])

    detail = client.get(f"/api/escalations/{newest['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["trace"] is not None
    assert len(body["trace"]) >= 3  # classifier, planner, escalation
    assert body["handoff_packet"]["root_cause_hypothesis"] == "test root cause"
    assert body["handoff_packet"]["recommended_action"] == "test action"
