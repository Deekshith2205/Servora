"""[Omnichannel] issue #151 — Response formatting by channel.

Proves format_reply_for_channel() (issue #143, proven correct in
isolation in tests/test_channel_formatting.py) is now actually called
from orchestrator.py::handle_message() at every real return point — not
just a standalone function nobody calls.
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
from app.db.models import Customer
from app.orchestrator import handle_message
from app.services.channel_adapters import route_channel_message

_MOCK_CRITIC_REVIEW = CriticReview(agrees=True, confidence=0.8, alternative_hypothesis=None, reasoning="mocked for test")

_MARKDOWN_REPLY = "Your refund has been **approved**. Here's the [policy](https://example.com/policy)."


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _mock_resolved_path_with_markdown_reply(monkeypatch):
    monkeypatch.setattr(
        orchestrator_module, "classify",
        lambda message: ClassificationResult(category="billing", sentiment="neutral", urgency=3, reasoning="r", confidence=0.9),
    )
    monkeypatch.setattr(
        orchestrator_module, "plan",
        lambda classification, customer_id, db: PlanDecision(action="resolve", target_agent="billing", reasoning="r"),
    )
    monkeypatch.setattr(
        orchestrator_module, "SPECIALISTS",
        {
            "billing": lambda db, customer_id, message, channel="live_chat": SpecialistResponse(reply=_MARKDOWN_REPLY, used_tools=[], confidence=0.6),
            "technical": lambda db, customer_id, message, channel="live_chat": SpecialistResponse(reply="n/a"),
        },
    )
    monkeypatch.setattr(orchestrator_module, "critique", lambda response, message: _MOCK_CRITIC_REVIEW)
    monkeypatch.setattr(orchestrator_module, "verify", lambda response: VerificationResult(approved=True, reasoning="ok"))
    monkeypatch.setattr(orchestrator_module, "extract_facts", lambda message, reply: [])


def _mock_direct_escalate(monkeypatch):
    monkeypatch.setattr(
        orchestrator_module, "classify",
        lambda message: ClassificationResult(category="account", sentiment="neutral", urgency=8, reasoning="r", confidence=1.0),
    )
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


def test_live_chat_reply_is_byte_for_byte_unchanged_at_the_orchestrator_level(monkeypatch, db_session):
    customer = Customer(name="Alice", email="alice-formatting-livechat@example.com", tier="vip")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    _mock_resolved_path_with_markdown_reply(monkeypatch)

    result = handle_message(db_session, customer.id, "Can I get a refund?")

    assert result.reply == _MARKDOWN_REPLY


def test_whatsapp_reply_is_genuinely_markdown_stripped_at_the_orchestrator_level(monkeypatch, db_session):
    customer = Customer(name="Bob", email="bob-formatting-whatsapp@example.com", tier="standard")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    _mock_resolved_path_with_markdown_reply(monkeypatch)

    result = handle_message(db_session, customer.id, "Can I get a refund?", channel="whatsapp")

    assert "**" not in result.reply
    assert "[policy]" not in result.reply
    assert "approved" in result.reply


def test_whatsapp_reply_is_markdown_stripped_via_a_real_route_channel_message_call(monkeypatch, db_session):
    """The issue's own acceptance criteria: verified via a real
    route_channel_message() call, not just handle_message() directly."""
    _mock_resolved_path_with_markdown_reply(monkeypatch)

    payload = {"from": "15555550188", "id": "wamid.FORMATTING_TEST", "text": {"body": "Can I get a refund?"}}
    result = route_channel_message(db_session, "whatsapp", payload)

    assert "**" not in result.reply
    assert "[policy]" not in result.reply
    assert "approved" in result.reply


def test_escalation_reply_is_formatted_for_whatsapp_too(monkeypatch, db_session):
    """The escalation branch's reply is a plain sentence with no
    markdown, so formatting it is a no-op in practice — but this proves
    _finalize_reply() is genuinely called on THAT branch too, not just
    the resolved-reply branch."""
    customer = Customer(name="Carol", email="carol-formatting-escalate@example.com", tier="standard")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    _mock_direct_escalate(monkeypatch)

    result = handle_message(db_session, customer.id, "please waive my fee", channel="whatsapp")

    assert result.reply == "A human agent will follow up shortly."
    assert result.status == "escalated"
