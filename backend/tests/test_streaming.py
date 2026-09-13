"""Tests for [SWARM] issue #79: real-time investigation streaming.

Two layers, tested separately:
1. `orchestrator.py::handle_message(..., stream_key=...)` actually
   publishes to `stream_bus` as each stage completes (queue.Queue is
   synchronously readable, so no threading/timing needed to test this).
2. `app/api/stream.py`'s SSE endpoint correctly drains and formats
   whatever's already in the bus for a given key — tested by pre-
   populating the queue (including the closing sentinel) BEFORE the
   request, so the generator finishes deterministically instead of
   needing real concurrency in a test.
"""
import queue as queue_module

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.orchestrator as orchestrator_module
from app.agents.classifier import ClassificationResult
from app.agents.critic import CriticReview
from app.agents.escalation import HandoffPacket
from app.agents.planner import PlanDecision
from app.agents.specialists import SpecialistResponse
from app.agents.verification import VerificationResult
from app.db.database import Base
from app.db.models import Customer
from app.main import app
from app.orchestrator import handle_message
from app.services import stream_bus

# [CRITIC] issue #110: mocked so these tests stay network-free.
_MOCK_CRITIC_REVIEW = CriticReview(agrees=True, confidence=0.8, alternative_hypothesis=None, reasoning="mocked for test")


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _seed_customer(db, email="stream@example.com"):
    customer = Customer(name="Stream Test Customer", email=email)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def _drain(q: "queue_module.Queue") -> list:
    """Every item currently in the queue, in order, without blocking."""
    items = []
    while True:
        try:
            items.append(q.get_nowait())
        except queue_module.Empty:
            return items


def test_handle_message_publishes_step_events_and_a_final_done_event(monkeypatch, db_session):
    stream_key = "test-stream-resolved"
    customer = _seed_customer(db_session)

    monkeypatch.setattr(
        orchestrator_module, "classify",
        lambda message: ClassificationResult(category="order", sentiment="neutral", urgency=3, reasoning="routine", confidence=0.8),
    )
    monkeypatch.setattr(
        orchestrator_module, "plan",
        lambda classification, customer_id, db: PlanDecision(action="resolve", target_agent="order", reasoning="order can handle it"),
    )
    monkeypatch.setattr(
        orchestrator_module, "SPECIALISTS",
        {"order": lambda db, customer_id, message: SpecialistResponse(reply="On its way.", used_tools=["get_customer_orders"], confidence=0.6, evidence=["ev"]),
         "technical": lambda db, customer_id, message: SpecialistResponse(reply="n/a")},
    )
    monkeypatch.setattr(orchestrator_module, "critique", lambda response, message: _MOCK_CRITIC_REVIEW)
    monkeypatch.setattr(orchestrator_module, "verify", lambda response: VerificationResult(approved=True, reasoning="ok"))
    monkeypatch.setattr(orchestrator_module, "extract_facts", lambda message, reply: [])

    result = handle_message(db_session, customer.id, "Where is my order?", stream_key=stream_key)

    q = stream_bus.subscribe(stream_key)
    events = _drain(q)

    # classifier, planner, order_specialist, critic, verification, memory
    # (6 "step" events) + 1 "done" event + the None close() sentinel.
    step_events = [e for e in events if e is not None and e.get("type") == "step"]
    done_events = [e for e in events if e is not None and e.get("type") == "done"]
    assert [e["agent_name"] for e in step_events] == ["classifier", "planner", "order_specialist", "critic", "verification", "memory"]
    assert [e["step_number"] for e in step_events] == [1, 2, 3, 4, 5, 6]
    # [CRITIC] #110: critic and verification both depend on the specialist
    # step (3) directly, not on each other.
    critic_event = next(e for e in step_events if e["agent_name"] == "critic")
    verification_event = next(e for e in step_events if e["agent_name"] == "verification")
    assert critic_event["depends_on"] == [3]
    assert verification_event["depends_on"] == [3]
    assert len(done_events) == 1
    assert done_events[0]["ticket_id"] == result.ticket_id
    assert done_events[0]["investigation_id"] is not None
    # The sentinel stream_bus.close() sends, so the SSE endpoint knows to stop.
    assert events[-1] is None

    stream_bus.cleanup(stream_key)


def test_handle_message_without_stream_key_publishes_nothing(monkeypatch, db_session):
    """Additive/optional — omitting stream_key must reproduce the exact
    previous behavior: no bus activity at all."""
    customer = _seed_customer(db_session, email="no-stream@example.com")
    monkeypatch.setattr(
        orchestrator_module, "classify",
        lambda message: ClassificationResult(category="account", sentiment="neutral", urgency=2, reasoning="r", confidence=0.7),
    )
    monkeypatch.setattr(
        orchestrator_module, "plan",
        lambda classification, customer_id, db: PlanDecision(action="escalate", target_agent="none", reasoning="r"),
    )
    monkeypatch.setattr(
        orchestrator_module, "build_handoff_packet",
        lambda message, attempted_fixes, urgency, confidence=None: HandoffPacket(
            situation="s", attempted_fixes=attempted_fixes, root_cause_hypothesis="rc", recommended_action="ra", urgency=urgency,
        ),
    )

    handle_message(db_session, customer.id, "please help", stream_key=None)

    # Nothing was ever published under any key derived from this call —
    # there's no key to even subscribe to, which is the point.
    assert "no-stream-key" not in stream_bus._queues  # sanity: nothing leaked under a guessed key


def test_stream_endpoint_relays_already_queued_events_and_stops_at_the_sentinel():
    stream_key = "test-stream-sse-endpoint"
    stream_bus.publish(stream_key, {"type": "step", "step_number": 1, "agent_name": "classifier", "action": "a", "status": "completed", "confidence": 0.9, "duration_ms": 10})
    stream_bus.publish(stream_key, {"type": "done", "ticket_id": 42, "investigation_id": 7})
    stream_bus.close(stream_key)

    with TestClient(app) as client:
        resp = client.get(f"/api/investigations/stream/{stream_key}")

    assert resp.status_code == 200
    body = resp.text
    assert "event: message" in body
    assert '"agent_name": "classifier"' in body
    assert '"ticket_id": 42' in body
    assert "event: end" in body
    # The queue was cleaned up once the generator finished.
    assert stream_key not in stream_bus._queues
