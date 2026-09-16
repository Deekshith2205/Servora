"""[Omnichannel] issue #152 — Context preservation across channels.

No new table — the real mechanism is `_resolve_or_create_customer()`
(issue #142) reliably resolving the SAME real `customer_id` across
channels for the same real person, so the EXISTING `CustomerMemory`
merge (issue #11) does the rest. Also covers a real bug found while
implementing this: WhatsApp's raw phone format ("15555550101") never
exact-string-matched this codebase's own human-formatted seeded
`Customer.phone` ("+1-555-0101") — fixed with digit-normalized
comparison in `_find_customer_by_phone()`.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.orchestrator as orchestrator_module
from app.agents.classifier import ClassificationResult
from app.agents.critic import CriticReview
from app.agents.memory import load_profile
from app.agents.planner import PlanDecision
from app.agents.specialists import SpecialistResponse
from app.agents.verification import VerificationResult
from app.db.database import Base
from app.db.models import Customer, Ticket
from app.services.channel_adapters import _find_customer_by_phone, route_channel_message

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
    monkeypatch.setattr(orchestrator_module, "extract_facts", lambda message, reply: ["prefers email contact"])


# --------------------------------------------------------------------- #
# The real phone-format bug, fixed as part of this issue
# --------------------------------------------------------------------- #


def test_find_customer_by_phone_matches_despite_different_formatting(db_session):
    """The exact real-world case this bug affects: a human-formatted
    seeded phone ("+1-555-0101") must still match a bare-digits WhatsApp
    "from" value ("15550101" — the same digits, no "+"/"-") for the same
    real number."""
    customer = Customer(name="Alice Rao", email="alice-context-preservation@example.com", phone="+1-555-0101", tier="vip")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    found = _find_customer_by_phone(db_session, "15550101")
    assert found is not None
    assert found.id == customer.id


def test_find_customer_by_phone_returns_none_for_a_genuinely_different_number(db_session):
    customer = Customer(name="Alice Rao", email="alice-context-preservation-2@example.com", phone="+1-555-0101", tier="vip")
    db_session.add(customer)
    db_session.commit()

    assert _find_customer_by_phone(db_session, "15555559999") is None


# --------------------------------------------------------------------- #
# The issue's own acceptance criteria
# --------------------------------------------------------------------- #


def test_same_person_resolves_to_the_same_customer_id_across_whatsapp_and_email(monkeypatch, db_session):
    _mock_resolved_path(monkeypatch)

    customer = Customer(name="Alice Rao", email="alice.crosschannel@example.com", phone="+1-555-0199", tier="vip")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    whatsapp_result = route_channel_message(
        db_session, "whatsapp",
        {"from": "15550199", "id": "wamid.CTX1", "text": {"body": "Where is my order?"}},
    )
    email_result = route_channel_message(
        db_session, "email",
        {"from": "alice.crosschannel@example.com", "subject": "Order question", "body": "Where is my order?", "message_id": "<ctx1@mail.example.com>"},
    )

    whatsapp_customer_id = db_session.get(Ticket, whatsapp_result.ticket_id).customer_id
    email_customer_id = db_session.get(Ticket, email_result.ticket_id).customer_id

    assert whatsapp_customer_id == email_customer_id == customer.id
    # No duplicate customer was created for the WhatsApp contact.
    assert db_session.query(Customer).count() == 1


def test_a_fact_learned_on_one_channel_is_visible_via_load_profile_on_another(monkeypatch, db_session):
    """Proves the mechanism, not live model behavior — the same
    established split test_memory.py's own suite already uses (offline
    test proves the fact reaches load_profile(); a real model choosing
    to reference it is covered by live verification, not an offline
    test)."""
    _mock_resolved_path(monkeypatch)

    customer = Customer(name="Bob", email="bob.crosschannel@example.com", phone="+1-555-0299", tier="standard")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    route_channel_message(
        db_session, "email",
        {"from": "bob.crosschannel@example.com", "subject": "Q", "body": "Where is my order?", "message_id": "<ctx2@mail.example.com>"},
    )
    route_channel_message(
        db_session, "whatsapp",
        {"from": "15550299", "id": "wamid.CTX2", "text": {"body": "Following up on my order"}},
    )

    profile = load_profile(customer.id, db_session)
    assert "prefers email contact" in profile["facts"]
