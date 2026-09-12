"""Tests for orchestrator.handle_message()'s escalation wiring (issue #12).

Mocks each agent at the orchestrator boundary — same pattern as
test_health.py's end-to-end test — since each agent's own LLM/tool
details are covered by its own test file (test_classifier.py,
test_planner.py, test_specialists.py, test_verification.py,
test_escalation.py). This file is specifically about proving
orchestrator.py wires them together correctly: the right context reaches
build_handoff_packet() at each of the two escalation points, and the
resolved path carries no packet at all.
"""
from unittest.mock import MagicMock

import app.orchestrator as orchestrator_module
from app.agents.classifier import ClassificationResult
from app.agents.escalation import HandoffPacket
from app.agents.planner import PlanDecision
from app.agents.specialists import SpecialistResponse
from app.agents.verification import VerificationResult
from app.orchestrator import handle_message


def _classification(**overrides):
    defaults = dict(category="account", sentiment="neutral", urgency=7, reasoning="test reasoning")
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
    monkeypatch.setattr(orchestrator_module, "verify", lambda response: VerificationResult(approved=False, reasoning="too low"))

    captured = {}
    monkeypatch.setattr(orchestrator_module, "build_handoff_packet", _fake_build_packet(captured))

    result = handle_message(MagicMock(), 1, "something vague")

    assert result.status == "escalated"
    assert result.handoff_packet is not None
    assert captured["confidence"] == 0.2
    assert len(captured["attempted_fixes"]) == 4  # classifier, planner, specialist, verification


def test_resolved_path_has_no_handoff_packet(monkeypatch):
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
    monkeypatch.setattr(orchestrator_module, "verify", lambda response: VerificationResult(approved=True, reasoning="ok"))
    monkeypatch.setattr(orchestrator_module, "extract_facts", lambda message, reply: [])

    result = handle_message(MagicMock(), 1, "something")

    assert result.status == "resolved"
    assert result.handoff_packet is None
