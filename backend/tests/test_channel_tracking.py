"""[Omnichannel] issue #133 — conversation source tracking.

Proves what the issue's acceptance criteria call out explicitly:
1. Every Ticket/Investigation row gets a real, non-null channel_key.
2. handle_message() with no `channel` argument (every existing caller,
   every existing test) behaves byte-for-byte the same as before this
   issue — the additive/optional-param regression guard.
3. POST /api/chat persists a `channel` field from the request body onto
   the resulting Ticket/Investigation, and defaults to "live_chat" when
   omitted.
4. [SWARM] issue #88's parallel multi-specialist fan-out (a genuinely
   different code path through handle_message() — reconciliation step,
   different _persist_investigation() call site history) still tags a
   single, correct channel_key. This codebase's own track record
   (#86/#98) shows a multi-branch change reliably misses one path on the
   first pass if it isn't tested explicitly branch-by-branch — this test
   is exactly that check, done proactively rather than found live.
5. An arbitrary channel value the seeded Channel table doesn't know about
   is still accepted and stored as-is — #133 deliberately adds no
   validation against the Channel table (that's out of scope; a future
   channel-adapter/normalization issue owns real channel identity), so
   this locks in that documented scope rather than leaving it assumed.

Mocks each agent at the orchestrator boundary — same pattern
test_orchestrator.py, test_health.py, and test_parallel_specialists.py
already use — since this issue is about channel threading, not agent
behavior.
"""
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
from app.db.models import Customer, Investigation, Ticket
from app.main import app
from app.orchestrator import handle_message

_MOCK_CRITIC_REVIEW = CriticReview(agrees=True, confidence=0.8, alternative_hypothesis=None, reasoning="mocked for test")

client = TestClient(app)


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


def _mock_resolved_path(monkeypatch):
    monkeypatch.setattr(orchestrator_module, "classify", lambda message: _classification())
    monkeypatch.setattr(
        orchestrator_module,
        "plan",
        lambda classification, customer_id, db: PlanDecision(action="resolve", target_agent="technical", reasoning="try technical"),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "SPECIALISTS",
        {"technical": lambda db, customer_id, message: SpecialistResponse(reply="fixed it", used_tools=[], confidence=0.6)},
    )
    monkeypatch.setattr(orchestrator_module, "critique", lambda response, message: _MOCK_CRITIC_REVIEW)
    monkeypatch.setattr(orchestrator_module, "verify", lambda response: VerificationResult(approved=True, reasoning="ok"))
    monkeypatch.setattr(orchestrator_module, "extract_facts", lambda message, reply: [])


def _mock_direct_escalate(monkeypatch):
    monkeypatch.setattr(orchestrator_module, "classify", lambda message: _classification(urgency=8))
    monkeypatch.setattr(
        orchestrator_module,
        "plan",
        lambda classification, customer_id, db: PlanDecision(action="escalate", target_agent="none", reasoning="outside policy"),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "build_handoff_packet",
        lambda message, attempted_fixes, urgency, confidence=None: HandoffPacket(
            situation="s", attempted_fixes=attempted_fixes, root_cause_hypothesis="r", recommended_action="a", urgency=urgency,
        ),
    )


# --------------------------------------------------------------------- #
# handle_message() — default behavior unchanged, and real channel threading
# --------------------------------------------------------------------- #


def test_handle_message_with_no_channel_arg_defaults_to_live_chat(monkeypatch, db_session):
    """Regression guard: every pre-#133 caller (including every existing
    test in this suite) calls handle_message() without `channel` at
    all — this proves that still produces a real, correct "live_chat"
    row rather than erroring or leaving the column null."""
    customer = Customer(name="Alice Rao", email="alice-channel-default@example.com", tier="vip")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    _mock_resolved_path(monkeypatch)

    result = handle_message(db_session, customer.id, "something")

    ticket = db_session.get(Ticket, result.ticket_id)
    assert ticket.channel_key == "live_chat"

    investigation = db_session.query(Investigation).filter(Investigation.ticket_id == ticket.id).first()
    assert investigation is not None
    assert investigation.channel_key == "live_chat"


def test_handle_message_threads_a_real_channel_through_on_the_resolved_path(monkeypatch, db_session):
    customer = Customer(name="Alice Rao", email="alice-channel-resolved@example.com", tier="vip")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    _mock_resolved_path(monkeypatch)

    result = handle_message(db_session, customer.id, "something", channel="whatsapp")

    ticket = db_session.get(Ticket, result.ticket_id)
    assert ticket.channel_key == "whatsapp"

    investigation = db_session.query(Investigation).filter(Investigation.ticket_id == ticket.id).first()
    assert investigation.channel_key == "whatsapp"


def test_handle_message_threads_a_real_channel_through_on_direct_escalation(monkeypatch, db_session):
    customer = Customer(name="Bob", email="bob-channel-escalate@example.com", tier="standard")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    _mock_direct_escalate(monkeypatch)

    result = handle_message(db_session, customer.id, "please waive my fee", channel="email")

    ticket = db_session.get(Ticket, result.ticket_id)
    assert ticket.channel_key == "email"

    investigation = db_session.query(Investigation).filter(Investigation.ticket_id == ticket.id).first()
    assert investigation.channel_key == "email"


def test_handle_message_threads_a_real_channel_through_on_verification_failure_escalation(monkeypatch, db_session):
    customer = Customer(name="Carol", email="carol-channel-verify-fail@example.com", tier="standard")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    monkeypatch.setattr(orchestrator_module, "classify", lambda message: _classification())
    monkeypatch.setattr(
        orchestrator_module,
        "plan",
        lambda classification, customer_id, db: PlanDecision(action="resolve", target_agent="technical", reasoning="try technical"),
    )
    monkeypatch.setattr(
        orchestrator_module,
        "SPECIALISTS",
        {"technical": lambda db, customer_id, message: SpecialistResponse(reply="not sure", used_tools=[], confidence=0.2)},
    )
    monkeypatch.setattr(orchestrator_module, "critique", lambda response, message: _MOCK_CRITIC_REVIEW)
    monkeypatch.setattr(orchestrator_module, "verify", lambda response: VerificationResult(approved=False, reasoning="too low"))
    monkeypatch.setattr(
        orchestrator_module,
        "build_handoff_packet",
        lambda message, attempted_fixes, urgency, confidence=None: HandoffPacket(
            situation="s", attempted_fixes=attempted_fixes, root_cause_hypothesis="r", recommended_action="a", urgency=urgency,
        ),
    )

    result = handle_message(db_session, customer.id, "something vague", channel="instagram")

    ticket = db_session.get(Ticket, result.ticket_id)
    assert ticket.channel_key == "instagram"

    investigation = db_session.query(Investigation).filter(Investigation.ticket_id == ticket.id).first()
    assert investigation.channel_key == "instagram"


def test_handle_message_tags_a_single_channel_on_the_parallel_fan_out_path(monkeypatch, db_session):
    """[SWARM] #88's fan-out runs two specialists concurrently and merges
    them via a "reconciliation" step before the SAME single
    _persist_investigation() call the single-specialist path uses — this
    proves that call site still receives and stores the real `channel`,
    not just the two single-specialist branches already covered above."""
    customer = Customer(name="Dana", email="dana-channel-parallel@example.com", tier="standard")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    monkeypatch.setattr(
        orchestrator_module, "classify",
        lambda message: _classification(category="billing", urgency=8, reasoning="payment/order mismatch"),
    )
    monkeypatch.setattr(
        orchestrator_module, "plan",
        lambda classification, customer_id, db: PlanDecision(
            action="resolve", target_agent="billing", reasoning="spans billing and order", additional_agents=["order"],
        ),
    )
    monkeypatch.setattr(
        orchestrator_module, "SPECIALISTS",
        {
            "billing": lambda db, customer_id, message: SpecialistResponse(reply="billing reply", used_tools=[], confidence=0.9),
            "order": lambda db, customer_id, message: SpecialistResponse(reply="order reply", used_tools=[], confidence=0.6),
            "technical": lambda db, customer_id, message: SpecialistResponse(reply="n/a"),
        },
    )
    monkeypatch.setattr(orchestrator_module, "critique", lambda response, message: _MOCK_CRITIC_REVIEW)
    monkeypatch.setattr(orchestrator_module, "verify", lambda response: VerificationResult(approved=True, reasoning="ok"))
    monkeypatch.setattr(orchestrator_module, "extract_facts", lambda message, reply: [])

    result = handle_message(db_session, customer.id, "Payment deducted but order not created", channel="email")

    ticket = db_session.get(Ticket, result.ticket_id)
    assert ticket.channel_key == "email"

    investigation = db_session.query(Investigation).filter(Investigation.ticket_id == ticket.id).first()
    assert investigation.channel_key == "email"


def test_handle_message_accepts_an_arbitrary_channel_value_without_validation(monkeypatch, db_session):
    """#133 deliberately adds no validation against the seeded Channel
    table — a future normalization layer, not this issue, owns real
    channel identity. Locks in that documented scope rather than leaving
    it an untested assumption."""
    customer = Customer(name="Eve", email="eve-channel-arbitrary@example.com", tier="standard")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    _mock_resolved_path(monkeypatch)

    result = handle_message(db_session, customer.id, "something", channel="sms")

    ticket = db_session.get(Ticket, result.ticket_id)
    assert ticket.channel_key == "sms"


# --------------------------------------------------------------------- #
# POST /api/chat — the HTTP-level contract
# --------------------------------------------------------------------- #


def test_chat_endpoint_defaults_channel_to_live_chat_when_omitted(monkeypatch):
    monkeypatch.setattr(
        "app.orchestrator.classify",
        lambda message: ClassificationResult(category="order", sentiment="neutral", urgency=3, reasoning="mocked", confidence=0.9),
    )
    monkeypatch.setattr(
        "app.orchestrator.plan",
        lambda classification, customer_id, db: PlanDecision(action="resolve", target_agent="order", reasoning="mocked"),
    )
    mocked_specialist = lambda db, customer_id, message: SpecialistResponse(reply="mocked reply", used_tools=[], confidence=0.9)
    monkeypatch.setattr("app.orchestrator.SPECIALISTS", {"order": mocked_specialist, "technical": mocked_specialist})
    monkeypatch.setattr("app.orchestrator.critique", lambda response, message: _MOCK_CRITIC_REVIEW)
    monkeypatch.setattr("app.orchestrator.extract_facts", lambda message, reply: [])

    resp = client.post("/api/chat", json={"customer_id": 1, "message": "Where is my order?"})
    assert resp.status_code == 200
    ticket_id = resp.json()["ticket_id"]

    from app.db.database import SessionLocal
    real_db = SessionLocal()
    try:
        ticket = real_db.get(Ticket, ticket_id)
        assert ticket.channel_key == "live_chat"
    finally:
        real_db.close()


def test_chat_endpoint_persists_a_real_channel_from_the_request_body(monkeypatch):
    monkeypatch.setattr(
        "app.orchestrator.classify",
        lambda message: ClassificationResult(category="order", sentiment="neutral", urgency=3, reasoning="mocked", confidence=0.9),
    )
    monkeypatch.setattr(
        "app.orchestrator.plan",
        lambda classification, customer_id, db: PlanDecision(action="resolve", target_agent="order", reasoning="mocked"),
    )
    mocked_specialist = lambda db, customer_id, message: SpecialistResponse(reply="mocked reply", used_tools=[], confidence=0.9)
    monkeypatch.setattr("app.orchestrator.SPECIALISTS", {"order": mocked_specialist, "technical": mocked_specialist})
    monkeypatch.setattr("app.orchestrator.critique", lambda response, message: _MOCK_CRITIC_REVIEW)
    monkeypatch.setattr("app.orchestrator.extract_facts", lambda message, reply: [])

    resp = client.post("/api/chat", json={"customer_id": 1, "message": "Where is my order?", "channel": "whatsapp"})
    assert resp.status_code == 200
    ticket_id = resp.json()["ticket_id"]

    from app.db.database import SessionLocal
    real_db = SessionLocal()
    try:
        ticket = real_db.get(Ticket, ticket_id)
        assert ticket.channel_key == "whatsapp"

        investigation = real_db.query(Investigation).filter(Investigation.ticket_id == ticket_id).first()
        assert investigation.channel_key == "whatsapp"
    finally:
        real_db.close()
