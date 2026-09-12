"""Unit tests for the Classifier Agent (issue #3). Network-free — the LLM
call is mocked via monkeypatch so these run in CI without an API key. The
real-network check is backend/scripts/check_classifier.py, run manually.
"""
from types import SimpleNamespace

from app.agents import classifier
from app.agents.classifier import _ClassificationSchema, classify
from app.llm import LLMError


def _mock_llm(schema_instance):
    def _call(system_prompt, messages, response_schema=None, max_tokens=4096):
        return schema_instance

    return _call


def test_classify_maps_llm_output_through(monkeypatch):
    monkeypatch.setattr(
        classifier,
        "call_llm",
        _mock_llm(
            _ClassificationSchema(
                category="billing",
                sentiment="negative",
                urgency=8,
                reasoning="Customer reports being charged twice for the same order.",
                confidence=0.92,
            )
        ),
    )

    result = classify("I was charged twice for my smart watch order.")

    assert result.category == "billing"
    assert result.sentiment == "negative"
    assert result.urgency == 8
    assert result.confidence == 0.92
    assert "charged twice" in result.reasoning.lower() or "charged" in result.reasoning.lower()


def test_classify_falls_back_on_invalid_category(monkeypatch):
    # _ClassificationSchema's own Field(ge=1, le=10) would reject urgency=999
    # at construction, so this uses a duck-typed stand-in to simulate an
    # out-of-schema value slipping through — classify() must not crash and
    # must clamp/default it rather than trust it blindly.
    monkeypatch.setattr(
        classifier,
        "call_llm",
        _mock_llm(
            SimpleNamespace(
                category="not_a_real_category",
                sentiment="not_a_real_sentiment",
                urgency=999,
                reasoning="edge case",
                confidence=99.9,
            )
        ),
    )

    result = classify("anything")

    assert result.category == "general"
    assert result.sentiment == "neutral"
    assert result.urgency == 10  # clamped to the max, not left at 999
    assert result.confidence == 1.0  # clamped to the max

def _mock_llm_error():
    def _call(system_prompt, messages, response_schema=None, max_tokens=4096):
        raise LLMError("API unreachable")
    return _call

def test_classify_llmerror_fallback(monkeypatch):
    monkeypatch.setattr(classifier, "call_llm", _mock_llm_error())

    # Should match 'billing'
    result = classify("I have a question about my invoice")
    assert result.category == "billing"
    assert result.sentiment == "neutral"
    assert result.urgency == 5
    assert result.confidence == 0.0

    # Should match 'order'
    result2 = classify("Where is my delivery?")
    assert result2.category == "order"
    assert result2.confidence == 0.0

    # Should match 'booking'
    result3 = classify("I want to cancel my reservation")
    assert result3.category == "booking"
    assert result3.confidence == 0.0

    # General
    result4 = classify("Hello there")
    assert result4.category == "general"
    assert result4.confidence == 0.0
