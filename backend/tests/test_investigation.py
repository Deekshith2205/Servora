"""Tests for [FEATURE] "AI Investigation Board & Autonomous Reasoning
Timeline"'s backend persistence — orchestrator.py::_persist_investigation()
and the Investigation/InvestigationStep models it writes.

Same mocking convention as test_orchestrator.py (mock each agent at the
orchestrator boundary, use a real in-memory DB so what's actually
persisted can be verified) — this file is specifically about the NEW
Investigation/InvestigationStep rows, not re-testing the existing
Ticket/trace_json behavior test_orchestrator.py already covers.
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
from app.db.models import Customer, Investigation, InvestigationStep
from app.orchestrator import handle_message

# [CRITIC] issue #110: mocked so resolve-path tests here stay network-free.
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


def _seed_customer(db, name="Alice Rao", email="alice-inv@example.com"):
    customer = Customer(name=name, email=email, tier="vip")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def test_resolved_conversation_creates_an_investigation_linked_to_its_ticket(monkeypatch, db_session):
    customer = _seed_customer(db_session)

    monkeypatch.setattr(
        orchestrator_module, "classify",
        lambda message: ClassificationResult(category="billing", sentiment="negative", urgency=6, reasoning="dup charge", confidence=0.85),
    )
    monkeypatch.setattr(
        orchestrator_module, "plan",
        lambda classification, customer_id, db: PlanDecision(action="resolve", target_agent="billing", reasoning="billing can fix it"),
    )
    billing_specialist = lambda db, customer_id, message: SpecialistResponse(
        reply="Refunded the duplicate charge.",
        used_tools=["get_customer_orders", "check_payment_issue", "issue_refund"],
        confidence=0.9,
        root_cause="Duplicate payment detected for order 5 against original order 4.",
        resolution="Refunded the duplicate order.",
        evidence=[
            "Retrieved 2 order(s) for customer #1: #4, #5.",
            "Payment anomaly detected on order #5: duplicate_payment.",
            "Issued refund for order #5.",
        ],
    )
    monkeypatch.setattr(
        orchestrator_module, "SPECIALISTS",
        # "technical" included only because SPECIALISTS.get(key, SPECIALISTS["technical"])
        # evaluates the fallback eagerly even when "billing" is the key actually
        # used — a pre-existing orchestrator.py quirk, not exercised by this test.
        {"billing": billing_specialist, "technical": billing_specialist},
    )
    monkeypatch.setattr(orchestrator_module, "critique", lambda response, message: _MOCK_CRITIC_REVIEW)
    monkeypatch.setattr(orchestrator_module, "verify", lambda response: VerificationResult(approved=True, reasoning="grounded and acted"))
    monkeypatch.setattr(orchestrator_module, "extract_facts", lambda message, reply: [])

    result = handle_message(db_session, customer.id, "I was charged twice")

    assert result.status == "resolved"
    investigation = db_session.query(Investigation).filter_by(ticket_id=result.ticket_id).one()

    assert investigation.customer_id == customer.id
    assert investigation.status == "resolved"
    assert investigation.confidence_score == 0.9
    assert investigation.root_cause == "Duplicate payment detected for order 5 against original order 4."
    assert investigation.resolution == "Refunded the duplicate order."
    assert investigation.started_at is not None
    assert investigation.completed_at is not None
    assert investigation.completed_at >= investigation.started_at

    steps = (
        db_session.query(InvestigationStep)
        .filter_by(investigation_id=investigation.id)
        .order_by(InvestigationStep.step_number)
        .all()
    )
    # classifier, planner, billing_specialist, critic, verification, memory
    assert [s.agent_name for s in steps] == ["classifier", "planner", "billing_specialist", "critic", "verification", "memory"]
    assert [s.step_number for s in steps] == [1, 2, 3, 4, 5, 6]
    for s in steps:
        assert s.duration_ms >= 0
        assert s.status in ("completed", "failed")

    # [CRITIC] #110: critic AND verification both depend on the specialist
    # step directly (3), not on each other.
    critic_step = steps[3]
    assert critic_step.depends_on == [3]
    assert critic_step.critic_review is not None
    verification_step = steps[4]
    assert verification_step.depends_on == [3]

    specialist_step = steps[2]
    assert specialist_step.evidence == [
        "Retrieved 2 order(s) for customer #1: #4, #5.",
        "Payment anomaly detected on order #5: duplicate_payment.",
        "Issued refund for order #5.",
    ]
    assert specialist_step.confidence == 0.9
    assert "Duplicate payment" in specialist_step.action


def test_direct_escalation_creates_an_investigation_with_escalated_status(monkeypatch, db_session):
    customer = _seed_customer(db_session, email="bob-inv@example.com")

    monkeypatch.setattr(
        orchestrator_module, "classify",
        lambda message: ClassificationResult(category="account", sentiment="neutral", urgency=8, reasoning="repeat issue", confidence=0.7),
    )
    monkeypatch.setattr(
        orchestrator_module, "plan",
        lambda classification, customer_id, db: PlanDecision(action="escalate", target_agent="none", reasoning="outside policy"),
    )
    monkeypatch.setattr(
        orchestrator_module, "build_handoff_packet",
        lambda message, attempted_fixes, urgency, confidence=None: HandoffPacket(
            situation="Customer needs a policy exception.",
            attempted_fixes=attempted_fixes,
            root_cause_hypothesis="Requires authority the AI doesn't have.",
            recommended_action="Have a human review the exception request.",
            urgency=urgency,
        ),
    )

    result = handle_message(db_session, customer.id, "please grant an exception")

    assert result.status == "escalated"
    investigation = db_session.query(Investigation).filter_by(ticket_id=result.ticket_id).one()

    assert investigation.status == "escalated"
    assert investigation.root_cause == "Requires authority the AI doesn't have."
    assert investigation.resolution == "Have a human review the exception request."

    steps = (
        db_session.query(InvestigationStep)
        .filter_by(investigation_id=investigation.id)
        .order_by(InvestigationStep.step_number)
        .all()
    )
    assert [s.agent_name for s in steps] == ["classifier", "planner", "escalation"]
    assert steps[-1].evidence == [
        "Customer needs a policy exception.",
        "Requires authority the AI doesn't have.",
    ]


def test_verification_failure_escalation_also_creates_an_investigation(monkeypatch, db_session):
    customer = _seed_customer(db_session, email="carol-inv@example.com")

    monkeypatch.setattr(
        orchestrator_module, "classify",
        lambda message: ClassificationResult(category="technical", sentiment="neutral", urgency=3, reasoning="vague", confidence=0.5),
    )
    monkeypatch.setattr(
        orchestrator_module, "plan",
        lambda classification, customer_id, db: PlanDecision(action="resolve", target_agent="technical", reasoning="try technical"),
    )
    monkeypatch.setattr(
        orchestrator_module, "SPECIALISTS",
        {"technical": lambda db, customer_id, message: SpecialistResponse(reply="not sure", used_tools=[], confidence=0.2, evidence=[])},
    )
    monkeypatch.setattr(orchestrator_module, "critique", lambda response, message: _MOCK_CRITIC_REVIEW)
    monkeypatch.setattr(orchestrator_module, "verify", lambda response: VerificationResult(approved=False, reasoning="too low"))
    monkeypatch.setattr(
        orchestrator_module, "build_handoff_packet",
        lambda message, attempted_fixes, urgency, confidence=None: HandoffPacket(
            situation="s", attempted_fixes=attempted_fixes, root_cause_hypothesis="low confidence reply",
            recommended_action="human review needed", urgency=urgency,
        ),
    )

    result = handle_message(db_session, customer.id, "something vague")

    assert result.status == "escalated"
    investigation = db_session.query(Investigation).filter_by(ticket_id=result.ticket_id).one()
    assert investigation.status == "escalated"
    assert investigation.confidence_score == 0.2  # the specialist's confidence, not the classifier's

    steps = (
        db_session.query(InvestigationStep)
        .filter_by(investigation_id=investigation.id)
        .order_by(InvestigationStep.step_number)
        .all()
    )
    # [CRITIC] #110: the critic runs even on a path that ends up escalating
    # after a failed verification — it reviewed the specialist's response
    # before Verification ever ran, so its own step is unaffected either way.
    assert [s.agent_name for s in steps] == ["classifier", "planner", "technical_specialist", "critic", "verification", "escalation"]
    assert steps[4].status == "failed"  # verification step itself is marked failed
