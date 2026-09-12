"""Tests for customer memory (issue #11).

Pure merge/load logic is tested against a real in-memory SQLite DB (no
mocking needed — it's not LLM-dependent). extract_facts() is tested with
call_llm mocked, same pattern as tests/test_classifier.py.

The acceptance criteria ("ask about the same issue twice — the second
response should reference what was learned in the first") is proven at
the mechanism level: test_specialist_includes_known_profile_facts_in_llm_context
shows a previously stored fact actually reaches the second call's LLM
context. Whether a real model then chooses to reference it is a live
behavior — covered by scripts/check_memory.py, not by an offline test.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.memory import _ExtractedFacts, extract_facts, load_profile, merge_profile
from app.agents.specialists import resolve_billing
from app.db.database import Base
from app.db.models import Customer


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# load_profile / merge_profile — pure DB logic
# ---------------------------------------------------------------------------


def test_load_profile_unknown_customer_returns_empty_dict(db_session):
    assert load_profile(999, db_session) == {}


def test_merge_then_load_round_trip(db_session):
    merge_profile(1, ["prefers email contact"], db_session)
    assert load_profile(1, db_session) == {"facts": ["prefers email contact"]}


def test_merge_is_set_union_not_overwrite(db_session):
    merge_profile(1, ["prefers email contact"], db_session)
    merge_profile(1, ["was given a one-time late-fee waiver on 2024-01-01"], db_session)

    profile = load_profile(1, db_session)
    assert "prefers email contact" in profile["facts"]
    assert "was given a one-time late-fee waiver on 2024-01-01" in profile["facts"]
    assert len(profile["facts"]) == 2


def test_merge_deduplicates_repeated_facts(db_session):
    merge_profile(1, ["prefers email contact"], db_session)
    merge_profile(1, ["prefers email contact"], db_session)
    assert load_profile(1, db_session)["facts"].count("prefers email contact") == 1


def test_merge_empty_facts_is_a_noop_never_erases(db_session):
    """The core rule from docs/ARCHITECTURE.md: an empty/failed extraction
    must never erase a previously known fact."""
    merge_profile(1, ["prefers email contact"], db_session)
    merge_profile(1, [], db_session)  # simulates a turn with nothing durable extracted
    assert load_profile(1, db_session) == {"facts": ["prefers email contact"]}


# ---------------------------------------------------------------------------
# extract_facts — LLM call, mocked (same pattern as test_classifier.py)
# ---------------------------------------------------------------------------


def test_extract_facts_returns_llm_output(monkeypatch):
    import app.agents.memory as memory_module

    monkeypatch.setattr(
        memory_module,
        "call_llm",
        lambda system_prompt, messages, response_schema=None, max_tokens=4096: _ExtractedFacts(
            facts=["prefers a callback over email"]
        ),
    )
    assert extract_facts("Please don't email me, call instead.", "Noted, we'll call you.") == [
        "prefers a callback over email"
    ]


def test_extract_facts_empty_when_nothing_durable(monkeypatch):
    import app.agents.memory as memory_module

    monkeypatch.setattr(
        memory_module,
        "call_llm",
        lambda system_prompt, messages, response_schema=None, max_tokens=4096: _ExtractedFacts(facts=[]),
    )
    assert extract_facts("Where is order 5?", "It's still processing.") == []


# ---------------------------------------------------------------------------
# Acceptance criteria mechanism: a stored fact actually reaches the next
# specialist call's LLM context.
# ---------------------------------------------------------------------------


def _text(text: str):
    block = MagicMock()
    block.type, block.text = "text", text
    return block


def _response(content: list, stop_reason: str):
    resp = MagicMock()
    resp.content, resp.stop_reason = content, stop_reason
    return resp


@patch("app.llm._client", None)
def test_specialist_includes_known_profile_facts_in_llm_context(db_session):
    customer = Customer(name="Alice Rao", email="alice@example.com", tier="vip")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    # Simulate a fact already learned from an earlier turn.
    merge_profile(customer.id, ["was already told their order is delayed due to a warehouse issue"], db_session)

    captured_messages = []

    def capture_create(**kwargs):
        captured_messages.append(kwargs["messages"])
        return _response([_text("As I mentioned, your order is still delayed due to the warehouse issue.")],
                          "end_turn")

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = capture_create

    with patch("app.llm.get_client", return_value=mock_client):
        resolve_billing(db_session, customer.id, "Any update on my order?")

    sent_content = captured_messages[0][0]["content"]
    assert "was already told their order is delayed due to a warehouse issue" in sent_content
    assert f"Customer ID: {customer.id}" in sent_content
