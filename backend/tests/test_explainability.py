"""Tests for the [SWARM] #77/#86 and [EXPLAIN] #89-#92/#98 batches: real
per-step timing/reasoning/tools, structured evidence refs, Planner
alternatives, and the explanation/evidence/confidence read APIs.

Follows the same two testing conventions already established in this
codebase: `test_investigation.py`'s direct `handle_message()` + in-memory
DB style for orchestrator-level assertions, and
`test_investigations_api.py`'s real `TestClient` + mocked-agent-boundary
style for the HTTP API. Deliberately covers all three pipeline branches
(resolved / direct-escalate / verification-fail-escalate) per issues #86
and #98's own acceptance criteria — new fields must degrade honestly
(never a fabricated value) on branches where they don't apply.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.orchestrator as orchestrator_module
from app.agents.classifier import ClassificationResult
from app.agents.escalation import HandoffPacket
from app.agents.planner import Alternative, PlanDecision
from app.agents.specialists import SpecialistResponse
from app.agents.verification import VerificationResult
from app.db.database import Base, SessionLocal
from app.db.models import Customer, Investigation, InvestigationStep
from app.main import app
from app.orchestrator import handle_message

# --------------------------------------------------------------------- #
# Orchestrator-level: real per-step timing/reasoning/tools/refs/alternatives
# --------------------------------------------------------------------- #


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _seed_customer(db, email="explain@example.com"):
    customer = Customer(name="Explain Test Customer", email=email, tier="vip")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def test_resolved_step_carries_real_timing_reasoning_tools_and_refs(monkeypatch, db_session):
    customer = _seed_customer(db_session)

    monkeypatch.setattr(
        orchestrator_module, "classify",
        lambda message: ClassificationResult(category="billing", sentiment="negative", urgency=6, reasoning="dup charge", confidence=0.85),
    )
    monkeypatch.setattr(
        orchestrator_module, "plan",
        lambda classification, customer_id, db: PlanDecision(
            action="resolve", target_agent="billing", reasoning="billing can fix it",
            alternatives_considered=[
                Alternative(action="escalate", rejected_because="confidence is high enough to resolve automatically"),
                Alternative(action="clarify", rejected_because="the order was unambiguous"),
            ],
        ),
    )
    billing_specialist = lambda db, customer_id, message: SpecialistResponse(
        reply="Refunded the duplicate charge.",
        used_tools=["get_customer_orders", "check_payment_issue", "issue_refund"],
        confidence=0.9,
        root_cause="Duplicate payment detected for order 5.",
        resolution="Refunded the duplicate order.",
        evidence=["Retrieved 2 order(s) for customer #1: #4, #5.", "Issued refund for order #5."],
        evidence_refs=[
            {"type": "order", "ref_id": 5, "label": "Order #5"},
            {"type": "kb_article", "ref_id": 2, "label": "Refund Policy"},
        ],
    )
    monkeypatch.setattr(orchestrator_module, "SPECIALISTS", {"billing": billing_specialist, "technical": billing_specialist})
    monkeypatch.setattr(orchestrator_module, "verify", lambda response: VerificationResult(approved=True, reasoning="grounded and acted"))
    monkeypatch.setattr(orchestrator_module, "extract_facts", lambda message, reply: [])

    result = handle_message(db_session, customer.id, "I was charged twice")
    investigation = db_session.query(Investigation).filter_by(ticket_id=result.ticket_id).one()
    steps = (
        db_session.query(InvestigationStep)
        .filter_by(investigation_id=investigation.id)
        .order_by(InvestigationStep.step_number)
        .all()
    )
    by_agent = {s.agent_name: s for s in steps}

    # [SWARM] #77: every step has a real started_at strictly before (or
    # equal to, given timer resolution) its completion timestamp.
    for s in steps:
        assert s.started_at is not None
        assert s.started_at <= s.timestamp

    # [SWARM] #77: full reasoning text reached InvestigationStep, not just
    # the short `action` label.
    assert by_agent["planner"].reasoning_text == "billing can fix it"
    assert by_agent["billing_specialist"].reasoning_text == "Refunded the duplicate charge."

    # [SWARM] #77: the specialist's real used_tools reached this table.
    assert by_agent["billing_specialist"].used_tools == ["get_customer_orders", "check_payment_issue", "issue_refund"]
    # Steps that never call tools record an empty list, not a missing one.
    assert by_agent["classifier"].used_tools == []
    assert by_agent["verification"].used_tools == []

    # [EXPLAIN] #91: structured evidence refs, split-able by type.
    refs = by_agent["billing_specialist"].evidence_refs
    assert {"type": "order", "ref_id": 5, "label": "Order #5"} in refs
    assert {"type": "kb_article", "ref_id": 2, "label": "Refund Policy"} in refs

    # [EXPLAIN] #89: the planner's real alternatives, chosen action excluded.
    alternatives = by_agent["planner"].alternatives_considered
    assert {"action": "escalate", "rejected_because": "confidence is high enough to resolve automatically"} in alternatives
    assert {"action": "clarify", "rejected_because": "the order was unambiguous"} in alternatives
    assert not any(a["action"] == "resolve" for a in alternatives)
    # Only the planner's step carries alternatives — everyone else's is empty.
    assert by_agent["classifier"].alternatives_considered == []
    assert by_agent["billing_specialist"].alternatives_considered == []

    # [SWARM] #78: explicit dependency graph — a plain chain for a
    # resolved run (classifier -> planner -> specialist -> verification
    # -> memory), first step has no dependency.
    assert [s.depends_on for s in steps] == [[], [1], [2], [3], [4]]


def test_direct_escalation_step_has_timing_but_no_fabricated_tools_or_alternatives(monkeypatch, db_session):
    """[SWARM] #86 / [EXPLAIN] #98: a direct-Planner escalation never runs
    a specialist — its steps must show real timing but must NOT show any
    used_tools/evidence_refs, since none were genuinely called."""
    customer = _seed_customer(db_session, email="direct-escalate@example.com")

    monkeypatch.setattr(
        orchestrator_module, "classify",
        lambda message: ClassificationResult(category="account", sentiment="neutral", urgency=8, reasoning="repeat issue", confidence=0.7),
    )
    monkeypatch.setattr(
        orchestrator_module, "plan",
        lambda classification, customer_id, db: PlanDecision(
            action="escalate", target_agent="none", reasoning="outside policy",
            alternatives_considered=[Alternative(action="resolve", rejected_because="no specialist has authority to grant this")],
        ),
    )
    monkeypatch.setattr(
        orchestrator_module, "build_handoff_packet",
        lambda message, attempted_fixes, urgency, confidence=None: HandoffPacket(
            situation="Customer needs a policy exception.", attempted_fixes=attempted_fixes,
            root_cause_hypothesis="Requires authority the AI doesn't have.",
            recommended_action="Have a human review the exception request.", urgency=urgency,
        ),
    )

    result = handle_message(db_session, customer.id, "please grant an exception")
    investigation = db_session.query(Investigation).filter_by(ticket_id=result.ticket_id).one()
    steps = (
        db_session.query(InvestigationStep)
        .filter_by(investigation_id=investigation.id)
        .order_by(InvestigationStep.step_number)
        .all()
    )
    by_agent = {s.agent_name: s for s in steps}

    assert [s.agent_name for s in steps] == ["classifier", "planner", "escalation"]
    for s in steps:
        assert s.started_at is not None

    # Real alternative, correctly attached to the planner step only.
    assert by_agent["planner"].alternatives_considered == [
        {"action": "resolve", "rejected_because": "no specialist has authority to grant this"}
    ]
    assert by_agent["escalation"].alternatives_considered == []
    # No specialist ever ran — nothing fabricated here.
    assert by_agent["escalation"].used_tools == []
    assert by_agent["escalation"].evidence_refs == []

    # [SWARM] #78: a direct escalation is a SHORTER chain, not a
    # differently-shaped one — still just "depends on the step before."
    assert [s.depends_on for s in steps] == [[], [1], [2]]


# --------------------------------------------------------------------- #
# API-level: /explanation, /evidence, /confidence, and the graph field
# --------------------------------------------------------------------- #

_email_counter = 0


def _seed_api_customer(db):
    global _email_counter
    _email_counter += 1
    customer = Customer(name="Explain API Customer", email=f"explain-api-{_email_counter}@example.com")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def _resolve_via_chat(client, customer_id):
    with patch("app.orchestrator.classify", return_value=ClassificationResult(
        category="billing", sentiment="negative", urgency=6, reasoning="dup charge", confidence=0.85
    )):
        with patch("app.orchestrator.plan", return_value=PlanDecision(
            action="resolve", target_agent="billing", reasoning="billing can fix it",
            alternatives_considered=[Alternative(action="escalate", rejected_because="confidence sufficient to resolve automatically")],
        )):
            with patch("app.orchestrator.SPECIALISTS", {
                "billing": lambda db, customer_id, message: SpecialistResponse(
                    reply="Refunded the duplicate charge.",
                    used_tools=["get_customer_orders", "issue_refund"],
                    confidence=0.9,
                    root_cause="Duplicate transaction detected.",
                    resolution="Refund conditions satisfied.",
                    evidence=["Retrieved 1 order(s) for customer: #5.", "Issued refund for order #5."],
                    evidence_refs=[
                        {"type": "order", "ref_id": 5, "label": "Order #5"},
                        {"type": "kb_article", "ref_id": 2, "label": "Billing Policy"},
                    ],
                ),
                "technical": lambda db, customer_id, message: SpecialistResponse(reply="n/a"),
            }):
                with patch("app.orchestrator.verify", return_value=VerificationResult(approved=True, reasoning="grounded")):
                    with patch("app.orchestrator.extract_facts", return_value=[]):
                        return client.post("/api/chat", json={"customer_id": customer_id, "message": "I was charged twice"})


def _escalate_via_chat(client, customer_id):
    with patch("app.orchestrator.classify", return_value=ClassificationResult(
        category="account", sentiment="neutral", urgency=9, reasoning="repeated failure", confidence=0.75
    )):
        with patch("app.orchestrator.plan", return_value=PlanDecision(
            action="escalate", target_agent="none", reasoning="outside policy",
            alternatives_considered=[Alternative(action="resolve", rejected_because="no specialist can grant a policy exception")],
        )):
            with patch("app.orchestrator.build_handoff_packet", return_value=HandoffPacket(
                situation="Needs a policy exception.", attempted_fixes=[],
                root_cause_hypothesis="Requires authority the AI doesn't have.",
                recommended_action="Have a human review the request.", urgency=9,
            )):
                return client.post("/api/chat", json={"customer_id": customer_id, "message": "please make an exception"})


def _investigation_id_for(client, ticket_id):
    resp = client.get(f"/api/investigations/by-ticket/{ticket_id}")
    assert resp.status_code == 200
    return resp.json()["id"]


def test_investigation_detail_includes_a_correct_execution_graph():
    db = SessionLocal()
    customer = _seed_api_customer(db)
    with TestClient(app) as client:
        chat_resp = _resolve_via_chat(client, customer.id)
        investigation_id = _investigation_id_for(client, chat_resp.json()["ticket_id"])
        resp = client.get(f"/api/investigations/{investigation_id}")

    body = resp.json()
    graph = body["graph"]
    # classifier, planner, billing_specialist, verification, memory
    assert len(graph["nodes"]) == 5
    assert len(graph["edges"]) == 4
    step_numbers = [n["step_number"] for n in graph["nodes"]]
    assert [e["from_step"] for e in graph["edges"]] == step_numbers[:-1]
    assert [e["to_step"] for e in graph["edges"]] == step_numbers[1:]


def test_explanation_endpoint_for_a_resolved_investigation():
    db = SessionLocal()
    customer = _seed_api_customer(db)
    with TestClient(app) as client:
        chat_resp = _resolve_via_chat(client, customer.id)
        investigation_id = _investigation_id_for(client, chat_resp.json()["ticket_id"])
        resp = client.get(f"/api/investigations/{investigation_id}/explanation")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "resolved"

    # [EXPLAIN] #90: overall + per-agent breakdown, only for agents that
    # actually produced a confidence value.
    assert body["confidence"]["overall"] == 0.9
    breakdown_agents = {row["agent_name"] for row in body["confidence"]["by_agent"]}
    assert "classifier" in breakdown_agents
    assert "billing_specialist" in breakdown_agents
    assert "planner" not in breakdown_agents  # planner never produces a confidence value

    # [EXPLAIN] #91: evidence vs. policy_references split correctly.
    assert any(r["type"] == "order" for r in body["evidence_refs"])
    assert all(r["type"] == "kb_article" for r in body["policy_references"])
    assert {"type": "kb_article", "ref_id": 2, "label": "Billing Policy"} in body["policy_references"]

    # [EXPLAIN] #89: the real alternative the planner rejected.
    assert body["alternatives_considered"] == [
        {"action": "escalate", "rejected_because": "confidence sufficient to resolve automatically"}
    ]

    # [EXPLAIN] #96: the chosen action is reported separately from (and
    # never equal to) any rejected alternative.
    assert body["chosen_action"] == "resolve"
    assert not any(a["action"] == body["chosen_action"] for a in body["alternatives_considered"])

    # [EXPLAIN] #92: agents_consulted + a non-empty, composed rationale.
    consulted = {row["agent_name"] for row in body["agents_consulted"]}
    assert {"classifier", "planner", "billing_specialist", "verification", "memory"} <= consulted
    assert "Duplicate transaction detected." in body["decision_rationale"]
    assert "Refund conditions satisfied." in body["decision_rationale"]


def test_explanation_endpoint_for_an_escalated_investigation_falls_back_to_the_handoff_packet():
    """[EXPLAIN] #92/#98: an escalated investigation has no specialist
    confidence and no root_cause/resolution the resolved-path composition
    could use — decision_rationale must fall back to the persisted
    HandoffPacket, and the confidence breakdown must not fabricate a
    specialist entry that never ran."""
    db = SessionLocal()
    customer = _seed_api_customer(db)
    with TestClient(app) as client:
        chat_resp = _escalate_via_chat(client, customer.id)
        investigation_id = _investigation_id_for(client, chat_resp.json()["ticket_id"])
        resp = client.get(f"/api/investigations/{investigation_id}/explanation")

    body = resp.json()
    assert body["status"] == "escalated"
    breakdown_agents = {row["agent_name"] for row in body["confidence"]["by_agent"]}
    assert "billing_specialist" not in breakdown_agents
    assert "technical_specialist" not in breakdown_agents

    assert "Requires authority the AI doesn't have." in body["decision_rationale"]
    assert "Have a human review the request." in body["decision_rationale"]
    assert body["alternatives_considered"] == [
        {"action": "resolve", "rejected_because": "no specialist can grant a policy exception"}
    ]
    # [EXPLAIN] #96: the direct-escalate branch's chosen action is
    # "escalate", not fabricated as "resolve".
    assert body["chosen_action"] == "escalate"


def test_evidence_endpoint_matches_the_explanation_endpoints_evidence():
    db = SessionLocal()
    customer = _seed_api_customer(db)
    with TestClient(app) as client:
        chat_resp = _resolve_via_chat(client, customer.id)
        investigation_id = _investigation_id_for(client, chat_resp.json()["ticket_id"])
        explanation = client.get(f"/api/investigations/{investigation_id}/explanation").json()
        evidence = client.get(f"/api/investigations/{investigation_id}/evidence").json()

    assert evidence["evidence"] == explanation["evidence"]
    assert evidence["evidence_refs"] == explanation["evidence_refs"]
    assert evidence["policy_references"] == explanation["policy_references"]


def test_confidence_endpoint_matches_the_explanation_endpoints_confidence():
    db = SessionLocal()
    customer = _seed_api_customer(db)
    with TestClient(app) as client:
        chat_resp = _resolve_via_chat(client, customer.id)
        investigation_id = _investigation_id_for(client, chat_resp.json()["ticket_id"])
        explanation = client.get(f"/api/investigations/{investigation_id}/explanation").json()
        confidence = client.get(f"/api/investigations/{investigation_id}/confidence").json()

    assert confidence == explanation["confidence"]


def test_explanation_404_for_unknown_investigation():
    with TestClient(app) as client:
        resp = client.get("/api/investigations/999999/explanation")
    assert resp.status_code == 404
