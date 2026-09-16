"""[Omnichannel] issue #145 — source attribution.

A test matrix (not new production code) exercising route_channel_message()
for every non-Live-Chat channel across all 3 of orchestrator.py's real
pipeline branches (direct-escalate, verification-fail-escalate, resolve),
asserting Investigation.channel_key/channel_metadata are correct at every
one. This codebase's own track record (issues #86/#98) shows a
multi-call-site change reliably misses exactly one branch if it isn't
tested branch-by-branch — this is that check for the Omnichannel
threading work specifically (#132-#144), done proactively rather than
found live.

Live Chat's own 3-branch coverage already exists in
test_channel_tracking.py (issue #133) — not duplicated here.
"""
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
from app.db.database import Base
from app.db.models import Investigation, Ticket
from app.services.channel_adapters import route_channel_message

_MOCK_CRITIC_REVIEW = CriticReview(agrees=True, confidence=0.8, alternative_hypothesis=None, reasoning="mocked for test")

_PAYLOADS = {
    "whatsapp": {"from": "15555550199", "id": "wamid.MATRIX_TEST", "text": {"body": "test message"}},
    "instagram": {"sender": {"id": "ig_matrix_test"}, "message": {"mid": "ig_mid_matrix", "text": "test message"}},
    "messenger": {"sender": {"id": "fb_matrix_test"}, "message": {"mid": "m_matrix", "text": "test message"}},
    "email": {"from": "matrix@example.com", "subject": "Matrix test", "body": "test message", "message_id": "<matrix@mail.example.com>"},
}


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


def _mock_direct_escalate(monkeypatch):
    monkeypatch.setattr(orchestrator_module, "classify", lambda message: _classification(urgency=8))
    monkeypatch.setattr(
        orchestrator_module, "plan",
        lambda classification, customer_id, db: PlanDecision(action="escalate", target_agent="none", reasoning="outside policy"),
    )
    monkeypatch.setattr(
        orchestrator_module, "build_handoff_packet",
        lambda message, attempted_fixes, urgency, confidence=None: HandoffPacket(
            situation="s", attempted_fixes=attempted_fixes, root_cause_hypothesis="r", recommended_action="a", urgency=urgency,
        ),
    )


def _mock_verification_failure_escalate(monkeypatch):
    monkeypatch.setattr(orchestrator_module, "classify", lambda message: _classification())
    monkeypatch.setattr(
        orchestrator_module, "plan",
        lambda classification, customer_id, db: PlanDecision(action="resolve", target_agent="technical", reasoning="try technical"),
    )
    monkeypatch.setattr(
        orchestrator_module, "SPECIALISTS",
        {"technical": lambda db, customer_id, message, channel="live_chat": SpecialistResponse(reply="not sure", used_tools=[], confidence=0.2)},
    )
    monkeypatch.setattr(orchestrator_module, "critique", lambda response, message: _MOCK_CRITIC_REVIEW)
    monkeypatch.setattr(orchestrator_module, "verify", lambda response: VerificationResult(approved=False, reasoning="too low"))
    monkeypatch.setattr(
        orchestrator_module, "build_handoff_packet",
        lambda message, attempted_fixes, urgency, confidence=None: HandoffPacket(
            situation="s", attempted_fixes=attempted_fixes, root_cause_hypothesis="r", recommended_action="a", urgency=urgency,
        ),
    )


def _mock_resolved(monkeypatch):
    monkeypatch.setattr(orchestrator_module, "classify", lambda message: _classification())
    monkeypatch.setattr(
        orchestrator_module, "plan",
        lambda classification, customer_id, db: PlanDecision(action="resolve", target_agent="technical", reasoning="try technical"),
    )
    monkeypatch.setattr(
        orchestrator_module, "SPECIALISTS",
        {"technical": lambda db, customer_id, message, channel="live_chat": SpecialistResponse(reply="fixed it", used_tools=[], confidence=0.6)},
    )
    monkeypatch.setattr(orchestrator_module, "critique", lambda response, message: _MOCK_CRITIC_REVIEW)
    monkeypatch.setattr(orchestrator_module, "verify", lambda response: VerificationResult(approved=True, reasoning="ok"))
    monkeypatch.setattr(orchestrator_module, "extract_facts", lambda message, reply: [])


@pytest.mark.parametrize("channel", ["whatsapp", "instagram", "messenger", "email"])
def test_direct_escalation_attributes_the_correct_channel(monkeypatch, db_session, channel):
    _mock_direct_escalate(monkeypatch)

    result = route_channel_message(db_session, channel, _PAYLOADS[channel])

    ticket = db_session.get(Ticket, result.ticket_id)
    assert ticket.channel_key == channel
    investigation = db_session.query(Investigation).filter(Investigation.ticket_id == ticket.id).first()
    assert investigation.channel_key == channel
    assert investigation.status == "escalated"
    assert investigation.channel_metadata is not None  # every non-Live-Chat channel carries real metadata


@pytest.mark.parametrize("channel", ["whatsapp", "instagram", "messenger", "email"])
def test_verification_failure_escalation_attributes_the_correct_channel(monkeypatch, db_session, channel):
    _mock_verification_failure_escalate(monkeypatch)

    result = route_channel_message(db_session, channel, _PAYLOADS[channel])

    ticket = db_session.get(Ticket, result.ticket_id)
    assert ticket.channel_key == channel
    investigation = db_session.query(Investigation).filter(Investigation.ticket_id == ticket.id).first()
    assert investigation.channel_key == channel
    assert investigation.status == "escalated"
    assert investigation.channel_metadata is not None


@pytest.mark.parametrize("channel", ["whatsapp", "instagram", "messenger", "email"])
def test_resolved_path_attributes_the_correct_channel(monkeypatch, db_session, channel):
    _mock_resolved(monkeypatch)

    result = route_channel_message(db_session, channel, _PAYLOADS[channel])

    ticket = db_session.get(Ticket, result.ticket_id)
    assert ticket.channel_key == channel
    investigation = db_session.query(Investigation).filter(Investigation.ticket_id == ticket.id).first()
    assert investigation.channel_key == channel
    assert investigation.status == "resolved"
    assert investigation.channel_metadata is not None
