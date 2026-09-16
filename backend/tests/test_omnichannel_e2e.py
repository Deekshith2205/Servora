"""[Omnichannel] issue #164 — End-to-end validation.

A real integration test proving the full omnichannel flow — channel ->
normalization -> the EXISTING investigation pipeline -> every real
read surface — agree on the SAME real conversation, not just trusting
each phase's own isolated tests.

Honest scope note: the issue's own technical requirements also name
`GET /api/dashboard/omnichannel` — that endpoint does not exist yet
(it is issue #153, Phase 6, not part of this batch of work). This test
covers the three real, currently-existing surfaces instead: the Inbox
(#136), the Investigation detail endpoint, and Analytics'
`channel_metrics` (#158) — every surface that DOES exist today.

Uses the real shared test DB (`app.db.database.SessionLocal`, the same
one `conftest.py` points at) rather than an isolated in-memory engine,
specifically so `route_channel_message()` and the `TestClient` HTTP
calls below see the exact same data — the actual proof this is one
consistent system, not two DBs that happen to agree by construction.
"""
from fastapi.testclient import TestClient

import app.orchestrator as orchestrator_module
from app.agents.classifier import ClassificationResult
from app.agents.critic import CriticReview
from app.agents.planner import PlanDecision
from app.agents.specialists import SpecialistResponse
from app.agents.verification import VerificationResult
from app.db.database import SessionLocal
from app.main import app
from app.services.channel_adapters import route_channel_message

_MOCK_CRITIC_REVIEW = CriticReview(agrees=True, confidence=0.8, alternative_hypothesis=None, reasoning="mocked for test")

client = TestClient(app)


def _mock_resolved_path(monkeypatch):
    monkeypatch.setattr(
        orchestrator_module, "classify",
        lambda message: ClassificationResult(category="order", sentiment="neutral", urgency=3, reasoning="r", confidence=0.9),
    )
    monkeypatch.setattr(
        orchestrator_module, "plan",
        lambda classification, customer_id, db: PlanDecision(action="resolve", target_agent="technical", reasoning="r"),
    )
    monkeypatch.setattr(
        orchestrator_module, "SPECIALISTS",
        {"technical": lambda db, customer_id, message, channel="live_chat": SpecialistResponse(reply="fixed it", used_tools=[], confidence=0.6)},
    )
    monkeypatch.setattr(orchestrator_module, "critique", lambda response, message: _MOCK_CRITIC_REVIEW)
    monkeypatch.setattr(orchestrator_module, "verify", lambda response: VerificationResult(approved=True, reasoning="ok"))
    monkeypatch.setattr(orchestrator_module, "extract_facts", lambda message, reply: [])


def _run_channel_message_via_real_db(channel_key, payload):
    db = SessionLocal()
    try:
        result = route_channel_message(db, channel_key, payload)
        return result
    finally:
        db.close()


def test_whatsapp_conversation_agrees_across_inbox_investigation_and_analytics(monkeypatch):
    _mock_resolved_path(monkeypatch)

    payload = {"from": "15557778888", "id": "wamid.E2E_WHATSAPP", "text": {"body": "Where is my order?"}}
    result = _run_channel_message_via_real_db("whatsapp", payload)
    ticket_id = result.ticket_id
    assert ticket_id is not None

    # Surface 1: Inbox (#136) — the ticket shows up, correctly tagged.
    inbox_resp = client.get("/api/inbox", params={"channel": "whatsapp"})
    assert inbox_resp.status_code == 200
    inbox_row = next((r for r in inbox_resp.json() if r["id"] == ticket_id), None)
    assert inbox_row is not None
    assert inbox_row["channel_key"] == "whatsapp"

    # Surface 2: Investigation detail — same channel, same ticket.
    inv_resp = client.get(f"/api/investigations/by-ticket/{ticket_id}")
    assert inv_resp.status_code == 200
    assert inv_resp.json()["channel"] == "whatsapp"
    assert inv_resp.json()["ticket_id"] == ticket_id

    # Surface 3: Analytics channel_metrics (#158) — the real count
    # includes this conversation (>=1, since other tests/seed data may
    # also contribute whatsapp tickets in the same shared test DB).
    analytics_resp = client.get("/api/analytics/summary")
    assert analytics_resp.status_code == 200
    channel_metrics = {m["channel"]: m for m in analytics_resp.json()["channel_metrics"]}
    assert "whatsapp" in channel_metrics
    assert channel_metrics["whatsapp"]["total"] >= 1


def test_email_conversation_agrees_across_inbox_investigation_and_analytics(monkeypatch):
    _mock_resolved_path(monkeypatch)

    payload = {
        "from": "e2e-email-test@example.com",
        "subject": "Order question",
        "body": "Where is my order?",
        "message_id": "<e2e-test@mail.example.com>",
    }
    result = _run_channel_message_via_real_db("email", payload)
    ticket_id = result.ticket_id
    assert ticket_id is not None

    inbox_resp = client.get("/api/inbox", params={"channel": "email"})
    assert inbox_resp.status_code == 200
    inbox_row = next((r for r in inbox_resp.json() if r["id"] == ticket_id), None)
    assert inbox_row is not None
    assert inbox_row["channel_key"] == "email"

    inv_resp = client.get(f"/api/investigations/by-ticket/{ticket_id}")
    assert inv_resp.status_code == 200
    assert inv_resp.json()["channel"] == "email"

    analytics_resp = client.get("/api/analytics/summary")
    channel_metrics = {m["channel"]: m for m in analytics_resp.json()["channel_metrics"]}
    assert "email" in channel_metrics
    assert channel_metrics["email"]["total"] >= 1
