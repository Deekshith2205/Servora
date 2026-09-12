"""Unit tests for the Verification Agent (issue #10). No mocking needed —
verify() is a pure function, no LLM call involved.
"""
from app.agents.specialists import SpecialistResponse
from app.agents.verification import verify

# ---------------------------------------------------------------------------
# Acceptance criteria: a deliberately low-confidence response is caught.
# ---------------------------------------------------------------------------


def test_low_confidence_is_rejected():
    response = SpecialistResponse(reply="I'm not sure — could you clarify?", used_tools=[], confidence=0.2)
    result = verify(response)
    assert result.approved is False
    assert "0.2" in result.reasoning


def test_high_confidence_action_taken_is_approved():
    response = SpecialistResponse(
        reply="I found your duplicate charge and issued a refund — it will appear in 5-7 business days.",
        used_tools=["get_customer_orders", "search_kb", "issue_refund"],
        confidence=0.9,
    )
    result = verify(response)
    assert result.approved is True


def test_medium_confidence_grounded_info_is_approved():
    response = SpecialistResponse(
        reply="Your order is currently processing and was only charged once.",
        used_tools=["get_customer_orders"],
        confidence=0.6,
    )
    result = verify(response)
    assert result.approved is True


# ---------------------------------------------------------------------------
# Completed-action consistency check
# ---------------------------------------------------------------------------


def test_claimed_refund_without_the_tool_is_rejected():
    """The core hallucination guard: reply claims a completed action, but
    the tool that would back it up was never actually called."""
    response = SpecialistResponse(
        reply="I've issued a refund for your order.",
        used_tools=["get_customer_orders"],  # no issue_refund call
        confidence=0.6,
    )
    result = verify(response)
    assert result.approved is False
    assert "issue_refund" in result.reasoning


def test_claimed_refund_with_the_tool_is_approved():
    response = SpecialistResponse(
        reply="I've issued a refund for your order.",
        used_tools=["get_customer_orders", "issue_refund"],
        confidence=0.9,
    )
    result = verify(response)
    assert result.approved is True


def test_mentioning_refund_without_claiming_completion_is_not_flagged():
    """Regression test: a legitimate policy statement that merely mentions
    'refund' (without claiming one was completed) must NOT be rejected —
    this is the false-positive the narrow phrase list is designed to avoid."""
    response = SpecialistResponse(
        reply="Unfortunately, this order doesn't qualify for a refund per our policy.",
        used_tools=["get_customer_orders", "search_kb"],
        confidence=0.6,
    )
    result = verify(response)
    assert result.approved is True
