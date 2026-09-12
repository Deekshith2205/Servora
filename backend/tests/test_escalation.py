"""Unit tests for the Escalation Agent (issue #12). Network-free —
call_llm is mocked, same pattern as tests/test_classifier.py.
"""
import app.agents.escalation as escalation_module
from app.agents.escalation import _HandoffSchema, build_handoff_packet


def _mock_llm(schema_instance):
    def _call(system_prompt, messages, response_schema=None, max_tokens=4096):
        return schema_instance

    return _call


def test_build_handoff_packet_populates_all_fields(monkeypatch):
    monkeypatch.setattr(
        escalation_module,
        "call_llm",
        _mock_llm(
            _HandoffSchema(
                situation="Customer wants a late fee waived that's outside policy.",
                root_cause_hypothesis="The billing agent has no authority to grant this exception.",
                recommended_action="Have a human agent review the fee-waiver request.",
            )
        ),
    )

    packet = build_handoff_packet(
        message="Please waive my late fee",
        attempted_fixes=["classifier: billing, urgency 7", "planner: escalate — outside policy"],
        urgency=7,
    )

    assert packet.situation == "Customer wants a late fee waived that's outside policy."
    assert packet.attempted_fixes == ["classifier: billing, urgency 7", "planner: escalate — outside policy"]
    assert packet.root_cause_hypothesis == "The billing agent has no authority to grant this exception."
    assert packet.recommended_action == "Have a human agent review the fee-waiver request."
    assert packet.urgency == 7  # passed through untouched, not derived by this function


def test_build_handoff_packet_with_no_attempted_fixes_says_so_in_context(monkeypatch):
    captured = {}

    def _capture(system_prompt, messages, response_schema=None, max_tokens=4096):
        captured["content"] = messages[0]["content"]
        return _HandoffSchema(situation="s", root_cause_hypothesis="r", recommended_action="a")

    monkeypatch.setattr(escalation_module, "call_llm", _capture)

    packet = build_handoff_packet(message="test", attempted_fixes=[], urgency=5)

    assert "escalated immediately" in captured["content"].lower()
    assert packet.attempted_fixes == []


def test_build_handoff_packet_includes_confidence_in_context_when_given(monkeypatch):
    captured = {}

    def _capture(system_prompt, messages, response_schema=None, max_tokens=4096):
        captured["content"] = messages[0]["content"]
        return _HandoffSchema(situation="s", root_cause_hypothesis="r", recommended_action="a")

    monkeypatch.setattr(escalation_module, "call_llm", _capture)

    build_handoff_packet(message="test", attempted_fixes=["tried x"], urgency=5, confidence=0.2)

    assert "0.2" in captured["content"]


def test_build_handoff_packet_omits_confidence_line_when_not_given(monkeypatch):
    captured = {}

    def _capture(system_prompt, messages, response_schema=None, max_tokens=4096):
        captured["content"] = messages[0]["content"]
        return _HandoffSchema(situation="s", root_cause_hypothesis="r", recommended_action="a")

    monkeypatch.setattr(escalation_module, "call_llm", _capture)

    build_handoff_packet(message="test", attempted_fixes=["tried x"], urgency=5)

    assert "confidence" not in captured["content"].lower()
