"""Tests for orchestrator.handle_message()'s escalation wiring (issues
#12 and #14).

Mocks each agent at the orchestrator boundary — same pattern as
test_health.py's end-to-end test — since each agent's own LLM/tool
details are covered by its own test file (test_classifier.py,
test_planner.py, test_specialists.py, test_verification.py,
test_escalation.py). This file is specifically about proving
orchestrator.py wires them together correctly: the right context reaches
build_handoff_packet() at each of the two escalation points, the
resolved path carries no packet at all, and (issue #14) an escalation
actually persists a real Ticket row with the trace + packet attached.
"""
import json
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.orchestrator as orchestrator_module
from app.agents.classifier import ClassificationResult
from app.agents.critic import CriticReview
from app.agents.escalation import HandoffPacket
from app.agents.planner import PlanDecision
from app.agents.specialists import SpecialistResponse
from app.agents.verification import VerificationResult

# [CRITIC] issue #110: mocked so resolve-path tests here stay network-free.
_MOCK_CRITIC_REVIEW = CriticReview(agrees=True, confidence=0.8, alternative_hypothesis=None, reasoning="mocked for test")
from app.db.database import Base
from app.db.models import Customer, Ticket
from app.orchestrator import handle_message


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _classification(**overrides):
    defaults = dict(category="account", sentiment="neutral", urgency=7, reasoning="test reasoning", confidence=1.0)
    defaults.update(overrides)
    return ClassificationResult(**defaults)


def _fake_build_packet(captured):
    def _build(message, attempted_fixes, urgency, confidence=None):
        captured["attempted_fixes"] = attempted_fixes
        captured["urgency"] = urgency
        captured["confidence"] = confidence
        return HandoffPacket(
            situation="test situation",
            attempted_fixes=attempted_fixes,
            root_cause_hypothesis="test root cause",
            recommended_action="test action",
            urgency=urgency,
        )

    return _build


def test_planner_direct_escalate_produces_a_populated_handoff_packet(monkeypatch):
    monkeypatch.setattr(orchestrator_module, "classify", lambda message: _classification(urgency=8))
    monkeypatch.setattr(
        orchestrator_module,
        "plan",
        lambda classification, customer_id, db: PlanDecision(
            action="escalate", target_agent="none", reasoning="outside policy"
        ),
    )
    captured = {}
    monkeypatch.setattr(orchestrator_module, "build_handoff_packet", _fake_build_packet(captured))

    result = handle_message(MagicMock(), 1, "please waive my account closure fee")

    assert result.status == "escalated"
    assert result.handoff_packet is not None
    assert result.handoff_packet.root_cause_hypothesis == "test root cause"
    assert captured["confidence"] is None  # no specialist ever ran
    assert captured["urgency"] == 8
    assert len(captured["attempted_fixes"]) == 2  # classifier + planner reasoning only
    assert "test root cause" in result.trace[-1].output  # escalation trace step cites the packet


def test_verification_failure_escalate_produces_a_populated_handoff_packet_with_confidence(monkeypatch):
    monkeypatch.setattr(orchestrator_module, "classify", lambda message: _classification())
    monkeypatch.setattr(
        orchestrator_module,
        "plan",
        lambda classification, customer_id, db: PlanDecision(
            action="resolve", target_agent="technical", reasoning="try technical"
        ),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "SPECIALISTS",
        {"technical": lambda db, customer_id, message: SpecialistResponse(reply="not sure", used_tools=[], confidence=0.2)},
    )
    monkeypatch.setattr(orchestrator_module, "critique", lambda response, message: _MOCK_CRITIC_REVIEW)
    monkeypatch.setattr(orchestrator_module, "verify", lambda response: VerificationResult(approved=False, reasoning="too low"))

    captured = {}
    monkeypatch.setattr(orchestrator_module, "build_handoff_packet", _fake_build_packet(captured))

    result = handle_message(MagicMock(), 1, "something vague")

    assert result.status == "escalated"
    assert result.handoff_packet is not None
    assert captured["confidence"] == 0.2
    assert len(captured["attempted_fixes"]) == 5  # classifier, planner, specialist, critic, verification


def test_resolved_path_creates_a_real_ticket_and_has_no_handoff_packet(monkeypatch, db_session):
    customer = Customer(name="Alice Rao", email="alice@example.com", tier="vip")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    monkeypatch.setattr(orchestrator_module, "classify", lambda message: _classification())
    monkeypatch.setattr(
        orchestrator_module,
        "plan",
        lambda classification, customer_id, db: PlanDecision(
            action="resolve", target_agent="technical", reasoning="try technical"
        ),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "SPECIALISTS",
        {
            "technical": lambda db, customer_id, message: SpecialistResponse(
                reply="fixed it", used_tools=["search_kb"], confidence=0.6
            )
        },
    )
    monkeypatch.setattr(orchestrator_module, "critique", lambda response, message: _MOCK_CRITIC_REVIEW)
    monkeypatch.setattr(orchestrator_module, "verify", lambda response: VerificationResult(approved=True, reasoning="ok"))
    monkeypatch.setattr(orchestrator_module, "extract_facts", lambda message, reply: [])

    result = handle_message(db_session, customer.id, "something")

    assert result.status == "resolved"
    assert result.handoff_packet is None
    assert result.ticket_id is not None

    ticket = db_session.get(Ticket, result.ticket_id)
    assert ticket is not None
    assert ticket.customer_id == customer.id
    assert ticket.status == "resolved"
    assert ticket.handoff_packet_json is None
    trace = json.loads(ticket.trace_json)
    assert len(trace) > 0


# ---------------------------------------------------------------------------
# Issue #14: escalation actually persists a Ticket with trace + packet.
# Real in-memory DB here (not MagicMock) since we need to verify what was
# actually written, not just that a call happened.
# ---------------------------------------------------------------------------


def test_escalation_creates_a_real_ticket_with_trace_and_packet(monkeypatch, db_session):
    customer = Customer(name="Alice Rao", email="alice@example.com", tier="vip")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    monkeypatch.setattr(
        orchestrator_module,
        "classify",
        lambda message: ClassificationResult(category="account", sentiment="negative", urgency=9, reasoning="serious", confidence=0.8),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "plan",
        lambda classification, customer_id, db: PlanDecision(
            action="escalate", target_agent="none", reasoning="outside policy"
        ),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "build_handoff_packet",
        lambda message, attempted_fixes, urgency, confidence=None: HandoffPacket(
            situation="s", attempted_fixes=attempted_fixes, root_cause_hypothesis="r", recommended_action="a",
            urgency=urgency,
        ),
    )

    result = handle_message(db_session, customer.id, "please close my account and waive the fee")

    assert result.ticket_id is not None

    ticket = db_session.get(Ticket, result.ticket_id)
    assert ticket is not None
    assert ticket.customer_id == customer.id
    assert ticket.category == "account"
    assert ticket.sentiment == "negative"
    assert ticket.urgency == 9
    assert ticket.status == "escalated"
    assert ticket.message == "please close my account and waive the fee"

    trace = json.loads(ticket.trace_json)
    assert len(trace) == 3  # classifier, planner, escalation
    assert trace[0]["agent"] == "classifier"

    packet = json.loads(ticket.handoff_packet_json)
    assert packet["root_cause_hypothesis"] == "r"
    assert packet["recommended_action"] == "a"


def test_ticket_subject_is_truncated_for_a_long_message(monkeypatch, db_session):
    customer = Customer(name="Bob", email="bob2@example.com", tier="standard")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    long_message = "x" * 200

    monkeypatch.setattr(
        orchestrator_module,
        "classify",
        lambda message: ClassificationResult(category="general", sentiment="neutral", urgency=5, reasoning="r", confidence=0.9),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "plan",
        lambda classification, customer_id, db: PlanDecision(action="escalate", target_agent="none", reasoning="r"),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "build_handoff_packet",
        lambda message, attempted_fixes, urgency, confidence=None: HandoffPacket(
            situation="s", attempted_fixes=attempted_fixes, root_cause_hypothesis="r", recommended_action="a",
            urgency=urgency,
        ),
    )

    result = handle_message(db_session, customer.id, long_message)

    ticket = db_session.get(Ticket, result.ticket_id)
    assert len(ticket.subject) <= 80
    assert ticket.message == long_message  # full message preserved, only subject is truncated
