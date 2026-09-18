"""Tests for GET /api/escalations/{id} (issue #14).

Uses the real app + real DB via TestClient. A ticket that never went
through /api/chat (its trace_json/handoff_packet_json columns are left
at their default None) is the natural case for "trace/handoff_packet is
None" — created explicitly here rather than assumed from seed data,
since other test files running earlier in the same session (they all
share one file-based servora.db — see conftest.py's note) may have
already cleared the seeded tickets out from under this one.

[RBAC] issue #190/#196/#220: every escalation-queue endpoint here
(list/detail/assign/resolve.../close) checks permission BEFORE looking
up the ticket — even the "unknown ticket" 404 test needs valid staff
headers, or it would get a 403 first instead.
"""
from fastapi.testclient import TestClient

from app.agents.classifier import ClassificationResult
from app.agents.escalation import HandoffPacket
from app.agents.planner import PlanDecision
from app.db.database import SessionLocal
from app.db.models import Ticket
from app.main import app
from tests.rbac_headers import staff_headers

client = TestClient(app)


def _admin_headers():
    with SessionLocal() as db:
        headers = staff_headers(db, "administrator")
        db.close()
        return headers


def test_escalation_detail_404_for_missing_ticket():
    resp = client.get("/api/escalations/999999", headers=_admin_headers())
    assert resp.status_code == 404


def test_escalation_detail_for_a_ticket_with_no_trace_has_none_for_both():
    # A ticket that never went through /api/chat (e.g. created directly,
    # like the seeded demo tickets) has no trace_json/handoff_packet_json.
    with SessionLocal() as db:
        ticket = Ticket(customer_id=1, category="order", subject="no-trace ticket", message="m", status="open")
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        headers = staff_headers(db, "administrator")

        resp = client.get(f"/api/escalations/{ticket.id}", headers=headers)
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
    headers = _admin_headers()

    chat_resp = client.post("/api/chat", json={"customer_id": 1, "message": "please grant a policy exception"})
    assert chat_resp.status_code == 200

    escalations = client.get("/api/escalations", headers=headers).json()
    newest = max(escalations, key=lambda t: t["id"])

    detail = client.get(f"/api/escalations/{newest['id']}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["trace"] is not None
    assert len(body["trace"]) >= 3  # classifier, planner, escalation
    assert body["handoff_packet"]["root_cause_hypothesis"] == "test root cause"
    assert body["handoff_packet"]["recommended_action"] == "test action"


def test_list_resolved_tickets_excludes_open_and_escalated():
    with SessionLocal() as db:
        ticket_resolved = Ticket(customer_id=1, category="order", subject="resolved ticket", message="m", status="resolved")
        ticket_open = Ticket(customer_id=1, category="order", subject="open ticket", message="m", status="open")
        ticket_escalated = Ticket(customer_id=1, category="order", subject="escalated ticket", message="m", status="escalated")
        db.add_all([ticket_resolved, ticket_open, ticket_escalated])
        db.commit()

        # GET /api/tickets/resolved is not permission-gated — untouched by RBAC.
        resp = client.get("/api/tickets/resolved")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) >= 1
        assert any(t["subject"] == "resolved ticket" for t in body)
        assert all(t["status"] == "resolved" for t in body)

def test_list_escalations_excludes_resolved_and_closed():
    with SessionLocal() as db:
        ticket_resolved = Ticket(customer_id=1, category="order", subject="res", message="m", status="resolved")
        ticket_closed = Ticket(customer_id=1, category="order", subject="cls", message="m", status="closed")
        db.add_all([ticket_resolved, ticket_closed])
        db.commit()
        headers = staff_headers(db, "administrator")

        resp = client.get("/api/escalations", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert not any(t["status"] in ["resolved", "closed"] for t in body)


def test_list_escalations_without_permission_is_a_real_403():
    """[RBAC] issue #190/#196/#220: an anonymous caller (no identity
    headers) gets a real 403, not the real queue."""
    resp = client.get("/api/escalations")
    assert resp.status_code == 403


def test_escalation_detail_includes_customer_and_history():
    with SessionLocal() as db:
        from app.db.models import Customer
        customer = Customer(name="Test Customer", email="test@example.com", phone="123", tier="vip")
        db.add(customer)
        db.commit()
        db.refresh(customer)

        ticket1 = Ticket(customer_id=customer.id, category="order", subject="Past 1", message="m", status="resolved")
        ticket2 = Ticket(customer_id=customer.id, category="order", subject="Past 2", message="m", status="closed")
        ticket_main = Ticket(customer_id=customer.id, category="account", subject="Current", message="m", status="open")

        db.add_all([ticket1, ticket2, ticket_main])
        db.commit()
        db.refresh(ticket_main)
        headers = staff_headers(db, "administrator")

        resp = client.get(f"/api/escalations/{ticket_main.id}", headers=headers)
        assert resp.status_code == 200
        body = resp.json()

        assert body["customer"] is not None
        assert body["customer"]["name"] == "Test Customer"
        assert body["customer"]["tier"] == "vip"

        history = body["customer_history"]
        assert history is not None
        assert len(history) == 2
        # Ensure current ticket is not in history
        assert not any(h["id"] == ticket_main.id for h in history)


def test_assign_escalation():
    with SessionLocal() as db:
        ticket = Ticket(customer_id=1, category="order", subject="Assign test", message="m", status="open")
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        headers = staff_headers(db, "administrator")

        # Assign
        resp = client.post(f"/api/escalations/{ticket.id}/assign", json={"assigned_to": "Asha"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["assigned_to"] == "Asha"

        # Unassign
        resp = client.post(f"/api/escalations/{ticket.id}/assign", json={"assigned_to": None}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["assigned_to"] is None


def test_assign_escalation_validation():
    with SessionLocal() as db:
        ticket_resolved = Ticket(customer_id=1, category="order", subject="Assign valid", message="m", status="resolved")
        db.add(ticket_resolved)
        db.commit()
        db.refresh(ticket_resolved)
        headers = staff_headers(db, "administrator")

        # Cannot assign resolved
        resp = client.post(f"/api/escalations/{ticket_resolved.id}/assign", json={"assigned_to": "Asha"}, headers=headers)
        assert resp.status_code == 400

        ticket_open = Ticket(customer_id=1, category="order", subject="Assign valid", message="m", status="open")
        db.add(ticket_open)
        db.commit()
        db.refresh(ticket_open)

        # Empty string
        resp = client.post(f"/api/escalations/{ticket_open.id}/assign", json={"assigned_to": "   "}, headers=headers)
        assert resp.status_code == 400


def test_assign_escalation_without_permission_is_a_real_403():
    with SessionLocal() as db:
        ticket = Ticket(customer_id=1, category="order", subject="Assign test perm", message="m", status="open")
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        headers = staff_headers(db, "manager")  # can view the queue, but not act on it

        resp = client.post(f"/api/escalations/{ticket.id}/assign", json={"assigned_to": "Asha"}, headers=headers)
        assert resp.status_code == 403


def test_close_escalation():
    with SessionLocal() as db:
        ticket = Ticket(customer_id=1, category="order", subject="Close test", message="m", status="open")
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        headers = staff_headers(db, "administrator")

        resp = client.post(f"/api/escalations/{ticket.id}/close", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"


def test_close_escalation_validation():
    with SessionLocal() as db:
        ticket = Ticket(customer_id=1, category="order", subject="Close test 2", message="m", status="resolved")
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        headers = staff_headers(db, "administrator")

        resp = client.post(f"/api/escalations/{ticket.id}/close", headers=headers)
        assert resp.status_code == 400


def test_list_escalations_with_metrics():
    with SessionLocal() as db:
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        
        ticket_open = Ticket(customer_id=1, category="order", subject="Metrics open", message="m", status="open")
        ticket_resolved_today = Ticket(customer_id=1, category="order", subject="Metrics res today", message="m", status="resolved", resolved_at=now)
        ticket_resolved_yesterday = Ticket(customer_id=1, category="order", subject="Metrics res yes", message="m", status="resolved", resolved_at=yesterday)
        
        db.add_all([ticket_open, ticket_resolved_today, ticket_resolved_yesterday])
        db.commit()
        headers = staff_headers(db, "administrator")

        # Test without metrics (backwards compatible)
        resp1 = client.get("/api/escalations", headers=headers)
        assert resp1.status_code == 200
        body1 = resp1.json()
        assert isinstance(body1, list)
        
        # Test with metrics
        resp2 = client.get("/api/escalations?include_metrics=true", headers=headers)
        assert resp2.status_code == 200
        body2 = resp2.json()
        assert isinstance(body2, dict)
        assert "value" in body2
        assert "today_resolved_count" in body2
        assert isinstance(body2["value"], list)
        
        # Open ticket should be in the value list
        assert any(t["subject"] == "Metrics open" for t in body2["value"])
        # Should not include resolved in the value list
        assert not any(t["status"] == "resolved" for t in body2["value"])
        
        # resolved count should include today but not yesterday
        # Since we might have other seeded tickets resolved today, we can't assert == 1,
        # but we can assert it's >= 1 and check that yesterday wasn't counted (harder to isolate in a shared DB without clearing).
        # We know at least ticket_resolved_today is there.
        assert body2["today_resolved_count"] >= 1
