"""Tests for [FEATURE] Investigation Board's read-only API
(app/api/investigations.py). Uses the real app + real DB via TestClient
(`with TestClient(app) as client:` — required so the lifespan actually
runs, per conftest.py's own note) and drives real /api/chat conversations
(agents mocked at the same boundary test_health.py/test_orchestrator.py
already use) so what's asserted is what a real request would actually
produce, not a hand-built fixture.
"""
from unittest.mock import patch

from app.agents.classifier import ClassificationResult
from app.agents.critic import CriticReview
from app.agents.escalation import HandoffPacket
from app.agents.planner import PlanDecision
from app.agents.specialists import SpecialistResponse
from app.db.database import SessionLocal
from app.db.models import Customer
from app.main import app
from fastapi.testclient import TestClient
from tests.rbac_headers import staff_headers

# [RBAC] issue #187/#194/#217: list/metrics are permission-gated up
# front (a real 403 for an anonymous actor), and the detail/by-ticket
# lookups are gated inline via `can_view_investigation()` once the row
# is found — every call below that reaches a real row sends a real
# Administrator identity header. The two "unknown id" 404 tests are
# unaffected: the 404 raises before the permission check ever runs.

# [CRITIC] issue #110: mocked so resolve-path tests here stay network-free.
_MOCK_CRITIC_REVIEW = CriticReview(agrees=True, confidence=0.8, alternative_hypothesis=None, reasoning="mocked for test")

_email_counter = 0


def _seed_customer(db):
    global _email_counter
    _email_counter += 1
    customer = Customer(name="Investigation Test Customer", email=f"inv-api-test-{_email_counter}@example.com")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def _resolve_via_chat(client, customer_id):
    with patch("app.orchestrator.classify", return_value=ClassificationResult(
        category="order", sentiment="neutral", urgency=3, reasoning="routine", confidence=0.8
    )):
        with patch("app.orchestrator.plan", return_value=PlanDecision(
            action="resolve", target_agent="order", reasoning="order can handle it"
        )):
            with patch("app.orchestrator.SPECIALISTS", {
                "order": lambda db, customer_id, message, channel="live_chat": SpecialistResponse(
                    reply="Your order is on its way.",
                    used_tools=["get_customer_orders"],
                    confidence=0.6,
                    evidence=["Retrieved 1 order(s) for customer #1: #1."],
                ),
                "technical": lambda db, customer_id, message, channel="live_chat": SpecialistResponse(reply="n/a"),
            }):
                with patch("app.orchestrator.verify") as mock_verify:
                    from app.agents.verification import VerificationResult
                    mock_verify.return_value = VerificationResult(approved=True, reasoning="grounded")
                    with patch("app.orchestrator.critique", return_value=_MOCK_CRITIC_REVIEW):
                        with patch("app.orchestrator.extract_facts", return_value=[]):
                            return client.post("/api/chat", json={"customer_id": customer_id, "message": "Where is my order?"})


def _escalate_via_chat(client, customer_id):
    with patch("app.orchestrator.classify", return_value=ClassificationResult(
        category="account", sentiment="neutral", urgency=9, reasoning="repeated failure", confidence=0.75
    )):
        with patch("app.orchestrator.plan", return_value=PlanDecision(
            action="escalate", target_agent="none", reasoning="outside policy"
        )):
            with patch("app.orchestrator.build_handoff_packet", return_value=HandoffPacket(
                situation="s", attempted_fixes=[], root_cause_hypothesis="policy exception needed",
                recommended_action="human review", urgency=9,
            )):
                return client.post("/api/chat", json={"customer_id": customer_id, "message": "please make an exception"})


def test_get_investigation_by_id_for_a_resolved_conversation():
    db = SessionLocal()
    customer = _seed_customer(db)
    headers = staff_headers(db, "administrator")

    with TestClient(app) as client:
        chat_resp = _resolve_via_chat(client, customer.id)
        assert chat_resp.status_code == 200
        ticket_id = chat_resp.json()["ticket_id"]

        by_ticket = client.get(f"/api/investigations/by-ticket/{ticket_id}", headers=headers)
        assert by_ticket.status_code == 200
        investigation_id = by_ticket.json()["id"]

        resp = client.get(f"/api/investigations/{investigation_id}", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["ticket_id"] == ticket_id
    assert body["status"] == "resolved"
    assert body["confidence"] == 0.6
    agent_names = [step["agent_name"] for step in body["timeline"]]
    assert agent_names == ["classifier", "planner", "order_specialist", "critic", "verification", "memory"]
    assert "Retrieved 1 order(s) for customer #1: #1." in body["evidence"]


def test_get_investigation_404_for_unknown_id():
    with TestClient(app) as client:
        resp = client.get("/api/investigations/999999")
    assert resp.status_code == 404


def test_get_investigation_by_ticket_404_when_no_investigation_exists():
    with TestClient(app) as client:
        resp = client.get("/api/investigations/by-ticket/999999")
    assert resp.status_code == 404


def test_list_investigations_includes_recent_ones():
    db = SessionLocal()
    customer = _seed_customer(db)
    headers = staff_headers(db, "administrator")

    with TestClient(app) as client:
        chat_resp = _escalate_via_chat(client, customer.id)
        ticket_id = chat_resp.json()["ticket_id"]

        resp = client.get("/api/investigations", headers=headers)

    assert resp.status_code == 200
    ticket_ids = [row["ticket_id"] for row in resp.json()]
    assert ticket_id in ticket_ids
    matching = next(row for row in resp.json() if row["ticket_id"] == ticket_id)
    assert matching["status"] == "escalated"
    assert matching["root_cause"] == "policy exception needed"


def test_agent_performance_metrics_reflects_recorded_steps():
    db = SessionLocal()
    customer = _seed_customer(db)
    headers = staff_headers(db, "administrator")

    with TestClient(app) as client:
        _resolve_via_chat(client, customer.id)
        resp = client.get("/api/investigations/metrics/agents", headers=headers)

    assert resp.status_code == 200
    agent_names = {row["agent_name"] for row in resp.json()["agents"]}
    assert "classifier" in agent_names
    assert "order_specialist" in agent_names
    for row in resp.json()["agents"]:
        assert row["total_steps"] >= 1
        assert row["avg_duration_ms"] >= 0
