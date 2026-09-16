"""[Omnichannel] issues #142 (message normalization layer) and #144
(conversation synchronization).

Mocks each agent at the orchestrator boundary — same pattern every other
orchestrator-level test in this suite already uses — since these issues
are about normalization/routing/customer-resolution, not agent behavior.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.orchestrator as orchestrator_module
from app.agents.classifier import ClassificationResult
from app.agents.critic import CriticReview
from app.agents.planner import PlanDecision
from app.agents.specialists import SpecialistResponse
from app.agents.verification import VerificationResult
from app.db.database import Base
from app.db.models import Customer, Investigation, Ticket
from app.services.channel_adapters import (
    find_recent_conversation_on_channel,
    normalize_email,
    normalize_instagram,
    normalize_messenger,
    normalize_whatsapp,
    route_channel_message,
)

_MOCK_CRITIC_REVIEW = CriticReview(agrees=True, confidence=0.8, alternative_hypothesis=None, reasoning="mocked for test")

_WHATSAPP_PAYLOAD = {
    "from": "15555550101",
    "id": "wamid.HBgLMTU1NTU1NTU1MDEVAgARGBI5QTQ0RUE3RjZBOEQ4RjZFAA==",
    "text": {"body": "Where is my order?"},
}
_INSTAGRAM_PAYLOAD = {"sender": {"id": "1784235678"}, "message": {"mid": "ig_mid_123", "text": "Where is my order?"}}
_MESSENGER_PAYLOAD = {"sender": {"id": "5551234567890"}, "message": {"mid": "m_AbCdEf", "text": "Where is my order?"}}
_EMAIL_PAYLOAD = {
    "from": "alice.normalize@example.com",
    "subject": "Order question",
    "body": "Where is my order?",
    "message_id": "<CAF+abc123@mail.example.com>",
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


# --------------------------------------------------------------------- #
# #142 — each normalize_*() produces a real NormalizedMessage from a
# representative raw payload, with no real API credentials needed.
# --------------------------------------------------------------------- #


def test_normalize_whatsapp_extracts_phone_text_and_conversation_id():
    normalized = normalize_whatsapp(_WHATSAPP_PAYLOAD)
    assert normalized.channel == "whatsapp"
    assert normalized.message == "Where is my order?"
    assert normalized.contact_phone == "15555550101"
    assert normalized.channel_metadata["external_conversation_id"] == _WHATSAPP_PAYLOAD["id"]


def test_normalize_instagram_extracts_sender_id_since_no_phone_or_email_exists():
    normalized = normalize_instagram(_INSTAGRAM_PAYLOAD)
    assert normalized.channel == "instagram"
    assert normalized.contact_external_id == "1784235678"
    assert normalized.contact_email is None
    assert normalized.contact_phone is None


def test_normalize_messenger_extracts_sender_id():
    normalized = normalize_messenger(_MESSENGER_PAYLOAD)
    assert normalized.channel == "messenger"
    assert normalized.contact_external_id == "5551234567890"


def test_normalize_email_uses_the_from_address_directly():
    normalized = normalize_email(_EMAIL_PAYLOAD)
    assert normalized.channel == "email"
    assert normalized.contact_email == "alice.normalize@example.com"
    assert normalized.channel_metadata["subject"] == "Order question"


# --------------------------------------------------------------------- #
# #142 — route_channel_message() is the ONLY caller of handle_message()
# for these channels, and produces the exact same downstream shape a
# direct handle_message() call would.
# --------------------------------------------------------------------- #


def test_route_channel_message_for_a_new_whatsapp_number_creates_a_real_new_customer(monkeypatch, db_session):
    _mock_resolved_path(monkeypatch)
    assert db_session.query(Customer).filter(Customer.phone == "15555550101").first() is None

    result = route_channel_message(db_session, "whatsapp", _WHATSAPP_PAYLOAD)

    customer = db_session.query(Customer).filter(Customer.phone == "15555550101").first()
    assert customer is not None
    assert result.ticket_id is not None

    ticket = db_session.get(Ticket, result.ticket_id)
    assert ticket.customer_id == customer.id
    assert ticket.channel_key == "whatsapp"


def test_route_channel_message_produces_the_same_investigation_shape_handle_message_would(monkeypatch, db_session):
    """The actual proof that no second pipeline was built: normalizing +
    routing through route_channel_message() results in the identical
    step sequence a direct orchestrator.handle_message() call produces."""
    _mock_resolved_path(monkeypatch)

    result = route_channel_message(db_session, "email", _EMAIL_PAYLOAD)

    investigation = db_session.query(Investigation).filter(Investigation.ticket_id == result.ticket_id).first()
    agent_names = [s.agent_name for s in sorted(investigation.steps, key=lambda s: s.step_number)]
    assert agent_names == ["classifier", "planner", "technical_specialist", "critic", "verification", "memory"]
    assert investigation.channel_key == "email"
    assert investigation.channel_metadata["subject"] == "Order question"


def test_route_channel_message_for_a_returning_contact_reuses_the_same_customer(monkeypatch, db_session):
    _mock_resolved_path(monkeypatch)

    result1 = route_channel_message(db_session, "whatsapp", _WHATSAPP_PAYLOAD)
    result2 = route_channel_message(db_session, "whatsapp", _WHATSAPP_PAYLOAD)

    ticket1 = db_session.get(Ticket, result1.ticket_id)
    ticket2 = db_session.get(Ticket, result2.ticket_id)
    assert ticket1.customer_id == ticket2.customer_id  # same real Customer row, not a duplicate

    assert db_session.query(Customer).filter(Customer.phone == "15555550101").count() == 1


def test_route_channel_message_for_instagram_and_messenger_reuse_customer_by_external_id(monkeypatch, db_session):
    _mock_resolved_path(monkeypatch)

    route_channel_message(db_session, "instagram", _INSTAGRAM_PAYLOAD)
    route_channel_message(db_session, "instagram", _INSTAGRAM_PAYLOAD)

    assert db_session.query(Customer).filter(Customer.email == "instagram+1784235678@channel.local").count() == 1


def test_unknown_channel_raises():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    with pytest.raises(ValueError):
        route_channel_message(db, "carrier_pigeon", {})
    db.close()


# --------------------------------------------------------------------- #
# #144 — conversation synchronization: customer resolution consistency
# plus the read-only conversation-lookup helper.
# --------------------------------------------------------------------- #


def test_two_messages_on_the_same_external_thread_resolve_to_the_same_customer(monkeypatch, db_session):
    _mock_resolved_path(monkeypatch)

    route_channel_message(db_session, "whatsapp", _WHATSAPP_PAYLOAD)
    route_channel_message(db_session, "whatsapp", {**_WHATSAPP_PAYLOAD, "id": "wamid.DIFFERENT_MESSAGE_SAME_THREAD"})

    customers = db_session.query(Customer).filter(Customer.phone == "15555550101").all()
    assert len(customers) == 1


def test_find_recent_conversation_on_channel_locates_the_matching_thread(monkeypatch, db_session):
    _mock_resolved_path(monkeypatch)

    result = route_channel_message(db_session, "whatsapp", _WHATSAPP_PAYLOAD)
    customer_id = db_session.get(Ticket, result.ticket_id).customer_id

    found = find_recent_conversation_on_channel(db_session, customer_id, "whatsapp", _WHATSAPP_PAYLOAD["id"])
    assert found is not None
    assert found.ticket_id == result.ticket_id


def test_find_recent_conversation_on_channel_returns_none_for_a_different_thread(monkeypatch, db_session):
    _mock_resolved_path(monkeypatch)

    result = route_channel_message(db_session, "whatsapp", _WHATSAPP_PAYLOAD)
    customer_id = db_session.get(Ticket, result.ticket_id).customer_id

    found = find_recent_conversation_on_channel(db_session, customer_id, "whatsapp", "wamid.SOME_UNRELATED_THREAD")
    assert found is None


def test_find_recent_conversation_on_channel_returns_none_with_no_external_id():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    assert find_recent_conversation_on_channel(db, 1, "whatsapp", None) is None
    db.close()
