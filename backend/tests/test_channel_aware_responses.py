"""[Omnichannel] issue #150 — Channel-aware responses.

Proves the two acceptance criteria: a specialist's real LLM context
includes the real channel (mirroring test_memory.py's own
`test_specialist_includes_known_profile_facts_in_llm_context` pattern
for verifying LLM context content), and the Planner's decision is
provably unaffected by channel alone — `plan()` is never even given a
channel, so this is structurally guaranteed, verified explicitly here
rather than left assumed.
"""
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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


def _text(text):
    block = MagicMock()
    block.type, block.text = "text", text
    return block


def _response(content, stop_reason):
    resp = MagicMock()
    resp.content, resp.stop_reason = content, stop_reason
    return resp


@patch("app.llm._client", None)
def test_specialist_includes_the_real_channel_in_llm_context(db_session):
    customer = Customer(name="Alice Rao", email="alice-channel-aware@example.com", tier="vip")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    captured_messages = []

    def capture_create(**kwargs):
        captured_messages.append(kwargs["messages"])
        return _response([_text("Sure, here's your billing update.")], "end_turn")

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = capture_create

    with patch("app.llm.get_client", return_value=mock_client):
        resolve_billing(db_session, customer.id, "What's my balance?", channel="whatsapp")

    sent_content = captured_messages[0][0]["content"]
    assert "Channel: whatsapp" in sent_content


@patch("app.llm._client", None)
def test_specialist_defaults_channel_to_live_chat_in_llm_context(db_session):
    customer = Customer(name="Bob", email="bob-channel-aware@example.com", tier="standard")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    captured_messages = []

    def capture_create(**kwargs):
        captured_messages.append(kwargs["messages"])
        return _response([_text("Sure, here's your billing update.")], "end_turn")

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = capture_create

    with patch("app.llm.get_client", return_value=mock_client):
        resolve_billing(db_session, customer.id, "What's my balance?")

    sent_content = captured_messages[0][0]["content"]
    assert "Channel: live_chat" in sent_content


def test_planner_is_never_given_a_channel():
    """Structural proof that channel cannot influence the Planner's
    resolve/escalate/clarify decision: plan()'s own signature has no
    channel parameter at all, so orchestrator.py cannot pass one even
    if it wanted to. Channel is context for HOW a specialist replies,
    never an input to WHETHER to resolve/clarify/escalate."""
    import inspect

    from app.agents.planner import plan

    params = list(inspect.signature(plan).parameters)
    assert "channel" not in params
