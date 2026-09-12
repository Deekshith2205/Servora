"""Unit tests for the Planner Agent (issue #4). Network-free — call_llm()
and the ticket-history lookup are both mocked. The real-network check is
scripts/check_planner.py, run manually.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.agents import planner
from app.agents.classifier import ClassificationResult
from app.agents.planner import _PlanSchema, plan
from app.db.models import Ticket


def _classification(**overrides):
    defaults = dict(category="order", sentiment="neutral", urgency=3, reasoning="test", confidence=1.0)
    defaults.update(overrides)
    return ClassificationResult(**defaults)


def _mock_llm(schema_instance):
    def _call(system_prompt, messages, response_schema=None, max_tokens=4096):
        return schema_instance

    return _call


def test_plan_resolve_routes_to_target_agent(monkeypatch):
    monkeypatch.setattr(planner, "load_profile", lambda customer_id, db: {})
    monkeypatch.setattr(planner.mock_tools, "get_customer_tickets", lambda db, customer_id: [])
    monkeypatch.setattr(
        planner,
        "call_llm",
        _mock_llm(_PlanSchema(action="resolve", target_agent="order", reasoning="simple status question")),
    )

    decision = plan(_classification(), customer_id=1, db=MagicMock())

    assert decision.action == "resolve"
    assert decision.target_agent == "order"


def test_plan_resolve_without_target_agent_fails_safe_to_escalate(monkeypatch):
    # If the LLM says "resolve" but somehow gives no real target, that's an
    # invalid state — must fail safe to escalation, not guess a specialist.
    monkeypatch.setattr(planner, "load_profile", lambda customer_id, db: {})
    monkeypatch.setattr(planner.mock_tools, "get_customer_tickets", lambda db, customer_id: [])
    monkeypatch.setattr(
        planner,
        "call_llm",
        _mock_llm(_PlanSchema(action="resolve", target_agent="none", reasoning="edge case")),
    )

    decision = plan(_classification(), customer_id=1, db=MagicMock())

    assert decision.action == "escalate"
    assert decision.target_agent == "none"


def test_plan_falls_back_on_invalid_action(monkeypatch):
    monkeypatch.setattr(planner, "load_profile", lambda customer_id, db: {})
    monkeypatch.setattr(planner.mock_tools, "get_customer_tickets", lambda db, customer_id: [])
    monkeypatch.setattr(
        planner,
        "call_llm",
        _mock_llm(SimpleNamespace(action="not_a_real_action", target_agent="billing", reasoning="edge case")),
    )

    decision = plan(_classification(), customer_id=1, db=MagicMock())

    assert decision.action == "escalate"  # safest default, never crashes


def test_plan_passes_ticket_history_into_the_llm_context(monkeypatch):
    # Acceptance criteria: repeated/unresolved history is a signal the
    # planner must actually see, not just urgency/sentiment in isolation.
    ticket = MagicMock(spec=Ticket)
    ticket.status, ticket.category, ticket.subject, ticket.urgency = "open", "billing", "Charged twice", 8

    monkeypatch.setattr(planner, "load_profile", lambda customer_id, db: {})
    monkeypatch.setattr(planner.mock_tools, "get_customer_tickets", lambda db, customer_id: [ticket])

    captured = {}

    def _capture_call_llm(system_prompt, messages, response_schema=None, max_tokens=4096):
        captured["context"] = messages[0]["content"]
        return _PlanSchema(action="escalate", target_agent="none", reasoning="repeat issue")

    monkeypatch.setattr(planner, "call_llm", _capture_call_llm)

    plan(_classification(category="billing"), customer_id=1, db=MagicMock())

    assert "Charged twice" in captured["context"]
    assert "billing" in captured["context"]
