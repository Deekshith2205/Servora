"""Tests for [SWARM] issue #88: genuine parallel multi-specialist
investigation. Planner can name `additional_agents` beyond its primary
`target_agent` for a genuinely cross-cutting issue (e.g. "payment
deducted but order not created" needs both Billing and Order); the
orchestrator then runs them concurrently and reconciles their findings
into one response before Verification/Escalation/Memory continue exactly
as they already do for a single specialist.
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
from app.db.models import Customer, Investigation, InvestigationStep
from app.orchestrator import handle_message

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


def _seed_customer(db, email="parallel@example.com"):
    customer = Customer(name="Parallel Test Customer", email=email)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def test_cross_cutting_issue_runs_two_specialists_and_reconciles_them(monkeypatch, db_session):
    customer = _seed_customer(db_session)

    monkeypatch.setattr(
        orchestrator_module, "classify",
        lambda message: ClassificationResult(category="billing", sentiment="negative", urgency=8, reasoning="payment/order mismatch", confidence=0.9),
    )
    monkeypatch.setattr(
        orchestrator_module, "plan",
        lambda classification, customer_id, db: PlanDecision(
            action="resolve", target_agent="billing", reasoning="spans billing and order",
            additional_agents=["order"],
        ),
    )
    monkeypatch.setattr(
        orchestrator_module, "SPECIALISTS",
        {
            "billing": lambda db, customer_id, message: SpecialistResponse(
                reply="The payment was charged successfully.", used_tools=["check_payment_issue"],
                confidence=0.9, root_cause="Payment succeeded.", evidence=["Payment confirmed."],
                evidence_refs=[{"type": "order", "ref_id": 5, "label": "Order #5"}],
            ),
            "order": lambda db, customer_id, message: SpecialistResponse(
                reply="No order record was ever created for this payment.", used_tools=["check_order_issue"],
                confidence=0.6, root_cause="Order creation failed after payment.", evidence=["No order found."],
                evidence_refs=[{"type": "order", "ref_id": 5, "label": "Order #5"}],
            ),
            "technical": lambda db, customer_id, message: SpecialistResponse(reply="n/a"),
        },
    )
    monkeypatch.setattr(orchestrator_module, "critique", lambda response, message: _MOCK_CRITIC_REVIEW)
    monkeypatch.setattr(orchestrator_module, "verify", lambda response: VerificationResult(approved=True, reasoning="grounded"))
    monkeypatch.setattr(orchestrator_module, "extract_facts", lambda message, reply: [])

    result = handle_message(db_session, customer.id, "Payment deducted but order not created")

    assert result.status == "resolved"
    # [SWARM] issue #88: the reply reflects BOTH specialists, clearly labeled.
    assert "Billing specialist:" in result.reply
    assert "Order specialist:" in result.reply
    assert "charged successfully" in result.reply
    assert "No order record" in result.reply

    investigation = db_session.query(Investigation).filter_by(ticket_id=result.ticket_id).one()
    steps = (
        db_session.query(InvestigationStep)
        .filter_by(investigation_id=investigation.id)
        .order_by(InvestigationStep.step_number)
        .all()
    )
    by_agent = {s.agent_name: s for s in steps}

    assert set(by_agent) == {"classifier", "planner", "billing_specialist", "order_specialist", "reconciliation", "critic", "verification", "memory"}

    # [CRITIC] #110: the critic reviews the RECONCILED response (what
    # Verification sees), not either individual specialist — it depends
    # on the reconciliation step, same as verification does.
    reconciliation_step_number = by_agent["reconciliation"].step_number
    assert by_agent["critic"].depends_on == [reconciliation_step_number]
    assert by_agent["verification"].depends_on == [reconciliation_step_number]

    planner_step_number = by_agent["planner"].step_number
    billing_step = by_agent["billing_specialist"]
    order_step = by_agent["order_specialist"]

    # [SWARM] issue #88: both specialists depend on the SAME planner step
    # (fan-out) — neither depends on the other.
    assert billing_step.depends_on == [planner_step_number]
    assert order_step.depends_on == [planner_step_number]

    # Reconciliation depends on BOTH specialist steps (fan-in).
    reconciliation_step = by_agent["reconciliation"]
    assert set(reconciliation_step.depends_on) == {billing_step.step_number, order_step.step_number}

    # [SWARM] issue #88: confidence is the MIN across specialists (0.6),
    # not an average or the primary specialist's own 0.9 — conservative
    # by design.
    assert investigation.confidence_score == 0.6
    assert reconciliation_step.confidence == 0.6

    # Evidence and evidence_refs from BOTH specialists made it through.
    assert "Payment confirmed." in reconciliation_step.evidence
    assert "No order found." in reconciliation_step.evidence
    assert set(reconciliation_step.used_tools) == {"check_payment_issue", "check_order_issue"}


def test_single_specialist_path_is_unaffected_by_the_fan_out_code(monkeypatch, db_session):
    """[SWARM] issue #88 is purely additive — the common case (no
    additional_agents) must produce byte-for-byte the same shape as
    before: no "reconciliation" step, no fan-out."""
    customer = _seed_customer(db_session, email="single@example.com")

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

    result = handle_message(db_session, customer.id, "Where is my order?")

    investigation = db_session.query(Investigation).filter_by(ticket_id=result.ticket_id).one()
    agent_names = [
        s.agent_name for s in
        db_session.query(InvestigationStep).filter_by(investigation_id=investigation.id).order_by(InvestigationStep.step_number).all()
    ]
    assert agent_names == ["classifier", "planner", "order_specialist", "critic", "verification", "memory"]
    assert "reconciliation" not in agent_names
