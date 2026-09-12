"""Tests for GET /api/escalations/{id} (issue #14).

Uses the real app + real DB via TestClient. A ticket that never went
through /api/chat (its trace_json/handoff_packet_json columns are left
at their default None) is the natural case for "trace/handoff_packet is
None" — created explicitly here rather than assumed from seed data,
since other test files running earlier in the same session (they all
share one file-based servora.db — see conftest.py's note) may have
already cleared the seeded tickets out from under this one.
"""
from fastapi.testclient import TestClient

from app.agents.classifier import ClassificationResult
from app.agents.escalation import HandoffPacket
from app.agents.planner import PlanDecision
from app.db.database import SessionLocal
from app.db.models import Ticket
from app.main import app

client = TestClient(app)


def test_escalation_detail_404_for_missing_ticket():
    resp = client.get("/api/escalations/999999")
    assert resp.status_code == 404


def test_escalation_detail_for_a_ticket_with_no_trace_has_none_for_both():
    # A ticket that never went through /api/chat (e.g. created directly,
    # like the seeded demo tickets) has no trace_json/handoff_packet_json.
    db = SessionLocal()
    ticket = Ticket(customer_id=1, category="order", subject="no-trace ticket", message="m", status="open")
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    resp = client.get(f"/api/escalations/{ticket.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["trace"] is None
    assert body["handoff_packet"] is None


def test_escalation_detail_for_a_real_escalation_has_trace_and_packet(monkeypatch):
    monkeypatch.setattr(
        "app.orchestrator.classify",
        lambda message: ClassificationResult(
            category="account", sentiment="neutral", urgency=8, reasoning="mocked for test", confidence=0.9
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


def test_list_resolved_tickets_excludes_open_and_escalated():
    db = SessionLocal()
    ticket_resolved = Ticket(customer_id=1, category="order", subject="resolved ticket", message="m", status="resolved")
    ticket_open = Ticket(customer_id=1, category="order", subject="open ticket", message="m", status="open")
    ticket_escalated = Ticket(customer_id=1, category="order", subject="escalated ticket", message="m", status="escalated")
    db.add_all([ticket_resolved, ticket_open, ticket_escalated])
    db.commit()
    
    resp = client.get("/api/tickets/resolved")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 1
    assert any(t["subject"] == "resolved ticket" for t in body)
    assert all(t["status"] == "resolved" for t in body)

def test_list_escalations_excludes_resolved():
    resp = client.get("/api/escalations")
    assert resp.status_code == 200
    body = resp.json()
    assert not any(t["status"] == "resolved" for t in body)
