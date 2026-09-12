from fastapi.testclient import TestClient

from app.agents.classifier import ClassificationResult
from app.agents.escalation import HandoffPacket
from app.agents.planner import PlanDecision
from app.agents.specialists import SpecialistResponse
from app.llm import LLMError
from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_chat_endpoint_runs_end_to_end(monkeypatch):
    # classifier.classify() (#3), planner.plan() (#4), every specialist
    # (#6-#9), verification (#10), and the memory-write step (#11) all
    # call the real LLM — mock all of them so this test stays network-free
    # and runs in CI without an API key. Any future agent that starts
    # calling the real LLM needs the same treatment here.
    monkeypatch.setattr(
        "app.orchestrator.classify",
        lambda message: ClassificationResult(
            category="order", sentiment="neutral", urgency=3, reasoning="mocked for test", confidence=0.9
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
    assert body["handoff_packet"] is None  # resolved path carries no packet
    # Found while wiring up the Investigation Board: ticket_id was computed
    # by the orchestrator (issue #14) but never actually returned by this
    # endpoint — the frontend had no way to link a reply to its ticket.
    assert body["ticket_id"] is not None


def test_chat_endpoint_exposes_handoff_packet_on_escalation(monkeypatch):
    """Issue #13: the API response must actually carry the structured
    packet on the escalated path, not just the generic reply string."""
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

    resp = client.post("/api/chat", json={"customer_id": 1, "message": "please grant a policy exception"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "escalated"
    assert body["handoff_packet"] is not None
    assert body["handoff_packet"]["root_cause_hypothesis"] == "test root cause"
    assert body["handoff_packet"]["recommended_action"] == "test action"
    assert body["handoff_packet"]["urgency"] == 8


def test_chat_endpoint_llm_error_becomes_502_not_an_unhandled_500(monkeypatch):
    """Found live with a real API key once the account ran out of credit:
    classify() degrades gracefully on its own (issue #57's fallback), but
    plan()/specialists/build_handoff_packet() don't, and this endpoint
    never caught LLMError at all — any of those failing crashed the whole
    request as an unhandled 500, which bypasses CORSMiddleware (the
    browser only ever sees an opaque "Failed to fetch", not the actual
    reason). Same regression-guard pattern already used for issue #18's
    POST /api/booking."""
    def _raise(classification, customer_id, db):
        raise LLMError("Anthropic API error (400): credit balance too low.")

    monkeypatch.setattr(
        "app.orchestrator.classify",
        lambda message: ClassificationResult(
            category="order", sentiment="neutral", urgency=3, reasoning="mocked for test", confidence=0.9
        ),
    )
    monkeypatch.setattr("app.orchestrator.plan", _raise)

    resp = client.post("/api/chat", json={"customer_id": 1, "message": "Where is my order?"})
    assert resp.status_code == 502
    assert "credit balance" in resp.json()["detail"]
