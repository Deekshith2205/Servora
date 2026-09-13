"""Unit tests for the Critic Agent (issue #109). Network-free — call_llm()
is mocked, same pattern as test_planner.py/test_verification.py.
"""
from app.agents import critic
from app.agents.critic import CriticReview, _CriticSchema, critique
from app.agents.specialists import SpecialistResponse
from app.llm import LLMError


def _mock_llm(schema_instance):
    def _call(system_prompt, messages, response_schema=None, max_tokens=4096):
        return schema_instance

    return _call


def _response(**overrides):
    defaults = dict(
        reply="Refunded the duplicate charge.",
        used_tools=["get_customer_orders", "issue_refund"],
        confidence=0.9,
        root_cause="Duplicate payment on order #5.",
        resolution="Refunded order #5.",
        evidence=["Retrieved order #5.", "Duplicate payment detected."],
    )
    defaults.update(overrides)
    return SpecialistResponse(**defaults)


def test_critique_agrees_case(monkeypatch):
    monkeypatch.setattr(
        critic, "call_llm",
        _mock_llm(_CriticSchema(agrees=True, confidence=0.85, alternative_hypothesis=None, reasoning="Evidence directly supports the duplicate-payment root cause.")),
    )

    review = critique(_response(), "I was charged twice")

    assert isinstance(review, CriticReview)
    assert review.agrees is True
    assert review.confidence == 0.85
    assert review.alternative_hypothesis is None
    assert "duplicate-payment" in review.reasoning


def test_critique_disagrees_case_includes_alternative_hypothesis(monkeypatch):
    monkeypatch.setattr(
        critic, "call_llm",
        _mock_llm(_CriticSchema(
            agrees=False, confidence=0.7,
            alternative_hypothesis="The charge may be a legitimate renewal, not a duplicate — no second order was actually created.",
            reasoning="The evidence only shows two orders exist, not that they were for the same purchase.",
        )),
    )

    review = critique(_response(), "I was charged twice")

    assert review.agrees is False
    assert review.alternative_hypothesis is not None
    assert "renewal" in review.alternative_hypothesis
    assert "two orders exist" in review.reasoning


def test_critique_never_includes_an_alternative_hypothesis_when_agreeing(monkeypatch):
    """Defensive: even if the LLM contradictorily fills in an alternative
    hypothesis while also agreeing, we don't propagate a confusing
    "agrees=True but here's an alternative" state — see critique()'s own
    normalization."""
    monkeypatch.setattr(
        critic, "call_llm",
        _mock_llm(_CriticSchema(agrees=True, confidence=0.6, alternative_hypothesis="stray text", reasoning="looks fine")),
    )

    review = critique(_response(), "I was charged twice")

    assert review.agrees is True
    assert review.alternative_hypothesis is None


def test_critique_confidence_is_clamped_to_0_1(monkeypatch):
    # `_CriticSchema.confidence` already has `ge=0.0, le=1.0` — a real
    # provider's structured output can't violate it — so the only way to
    # exercise critique()'s own defensive clamp (matching classifier.py's
    # identical belt-and-suspenders pattern) is to bypass validation with
    # `model_construct`, the same way an unusually permissive/buggy
    # provider response theoretically could.
    out_of_range = _CriticSchema.model_construct(agrees=True, confidence=1.5, alternative_hypothesis=None, reasoning="over-confident mock response")
    monkeypatch.setattr(critic, "call_llm", _mock_llm(out_of_range))

    review = critique(_response(), "test")

    assert review.confidence == 1.0


def test_critique_degrades_safely_when_the_llm_call_fails(monkeypatch):
    """Advisory agent, same fail-safe spirit as classifier.py: a critic
    that can't run must never break the caller, and must never fabricate
    a disagreement it didn't actually reach."""
    def _raise(*args, **kwargs):
        raise LLMError("mocked failure")

    monkeypatch.setattr(critic, "call_llm", _raise)

    review = critique(_response(), "test")

    assert review.agrees is True
    assert review.confidence == 0.0
    assert review.alternative_hypothesis is None
    assert "unavailable" in review.reasoning


def test_critique_does_not_see_the_specialists_own_confidence():
    """The prompt context must never leak the specialist's confidence —
    see critic.py's module docstring for why (the critic must review the
    claim, not defer to a number)."""
    context = critic._context_for(_response(confidence=0.9), "I was charged twice")
    assert "0.9" not in context
    assert "confidence" not in context.lower()
