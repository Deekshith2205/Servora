"""Unit tests for the Learning Agent (issue #17). Network-free — call_llm
is mocked, same pattern as tests/test_classifier.py.
"""
import app.agents.learning as learning_module
from app.agents.learning import _DraftSchema, draft_kb_article


def _mock_llm(schema_instance):
    def _call(system_prompt, messages, response_schema=None, max_tokens=4096):
        return schema_instance

    return _call


def test_draft_reusable_case_populates_all_fields(monkeypatch):
    monkeypatch.setattr(
        learning_module,
        "call_llm",
        _mock_llm(
            _DraftSchema(
                should_add=True,
                title="Legacy billing plan customers need manual migration before a refund",
                body="Customers still on the legacy billing plan cannot receive an automated refund; "
                "migrate them to the current plan first, then issue the refund normally.",
                tags=["billing", "refund"],
            )
        ),
    )

    draft = draft_kb_article(
        category="billing",
        customer_message="I was charged twice",
        resolution_notes="Migrated off the legacy plan, then refunded the duplicate charge.",
    )

    assert draft.should_add is True
    assert "legacy billing plan" in draft.title.lower()
    assert draft.tags == ["billing", "refund"]


def test_draft_one_off_case_is_not_suggested(monkeypatch):
    monkeypatch.setattr(
        learning_module,
        "call_llm",
        _mock_llm(_DraftSchema(should_add=False, title="", body="", tags=[])),
    )

    draft = draft_kb_article(
        category="billing",
        customer_message="Please waive my late fee this one time",
        resolution_notes="Granted a one-time goodwill waiver.",
    )

    assert draft.should_add is False
    assert draft.title == ""


def test_draft_includes_handoff_context_when_available(monkeypatch):
    captured = {}

    def _capture(system_prompt, messages, response_schema=None, max_tokens=4096):
        captured["content"] = messages[0]["content"]
        return _DraftSchema(should_add=False, title="", body="", tags=[])

    monkeypatch.setattr(learning_module, "call_llm", _capture)

    draft_kb_article(
        category="technical",
        customer_message="app crashes",
        resolution_notes="fixed",
        root_cause_hypothesis="unhandled null pointer on checkout",
        recommended_action="patch the checkout handler",
    )

    assert "unhandled null pointer" in captured["content"]
    assert "patch the checkout handler" in captured["content"]
