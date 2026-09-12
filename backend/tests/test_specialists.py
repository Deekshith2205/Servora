"""Tests for the Billing specialist agent (issue #6).

Network-free — only the Anthropic client is mocked (same pattern as
tests/test_tools.py for issue #5). Everything else — the DB session, the
tool registry, mock_tools — is real, so the integration tests below prove
the actual acceptance criteria: a scripted "double charge" conversation
really does flip the seeded order to `refunded` in the database, not just
that the right function was called.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.specialists import _estimate_confidence, resolve_billing
from app.db.database import Base
from app.db.models import Customer, KBArticle, Order

# ---------------------------------------------------------------------------
# Real (in-memory) DB fixture — isolated per test, no shared state with the
# app's own servora.db.
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _seed_billing_scenario(db):
    customer = Customer(name="Bob Nunez", email="bob@example.com", tier="standard")
    db.add(customer)
    db.flush()

    order = Order(customer_id=customer.id, product="Smart Watch", amount=249.00, status="processing")
    db.add(order)

    db.add(
        KBArticle(
            title="Refund policy",
            body="Refunds are issued to the original payment method within 5-7 business days "
            "once a duplicate charge or billing error is confirmed.",
            tags="billing,refund",
        )
    )
    db.commit()
    db.refresh(order)
    return customer, order


# ---------------------------------------------------------------------------
# Anthropic response builders — same shapes as test_tools.py
# ---------------------------------------------------------------------------


def _tool_use(id_: str, name: str, input_: dict):
    block = MagicMock()
    block.type, block.id, block.name, block.input = "tool_use", id_, name, input_
    return block


def _text(text: str):
    block = MagicMock()
    block.type, block.text = "text", text
    return block


def _response(content: list, stop_reason: str):
    resp = MagicMock()
    resp.content, resp.stop_reason = content, stop_reason
    return resp


# ---------------------------------------------------------------------------
# Confidence heuristic — pure function, no mocking needed
# ---------------------------------------------------------------------------


def test_confidence_high_when_action_tool_used():
    assert _estimate_confidence(["get_customer_orders", "search_kb", "issue_refund"]) == 0.9


def test_confidence_medium_when_only_grounding_tools_used():
    assert _estimate_confidence(["get_customer_orders", "search_kb"]) == 0.6


def test_confidence_low_when_no_tools_used():
    assert _estimate_confidence([]) == 0.2


# ---------------------------------------------------------------------------
# Acceptance criteria: "I was charged twice for my smart watch" actually
# refunds the seeded order and cites the refund policy.
# ---------------------------------------------------------------------------


@patch("app.llm._client", None)
def test_resolve_billing_double_charge_actually_refunds_the_order(db_session):
    customer, order = _seed_billing_scenario(db_session)
    assert order.status == "processing"  # sanity check before acting

    # Scripted conversation: look up orders -> confirm policy -> refund -> reply.
    responses = [
        _response([_tool_use("t1", "get_customer_orders", {"customer_id": customer.id})], "tool_use"),
        _response([_tool_use("t2", "search_kb", {"query": "refund policy"})], "tool_use"),
        _response([_tool_use("t3", "issue_refund", {"order_id": order.id})], "tool_use"),
        _response([_text("I found your duplicate charge on the Smart Watch order and issued a refund "
                          "per our refund policy — it will appear within 5-7 business days.")], "end_turn"),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("app.llm.get_client", return_value=mock_client):
        result = resolve_billing(db_session, customer.id, "I was charged twice for my smart watch")

    # The actual acceptance criteria: the DB row really changed.
    db_session.refresh(order)
    assert order.status == "refunded"

    assert result.used_tools == ["get_customer_orders", "search_kb", "issue_refund"]
    assert result.confidence == 0.9
    assert "refund" in result.reply.lower()


@patch("app.llm._client", None)
def test_resolve_billing_informational_only_does_not_refund(db_session):
    """When the model only looks things up and doesn't act, the order must
    stay untouched and confidence must reflect "grounded but no action"."""
    customer, order = _seed_billing_scenario(db_session)

    responses = [
        _response([_tool_use("t1", "get_customer_orders", {"customer_id": customer.id})], "tool_use"),
        _response([_text("Your Smart Watch order is still processing and was only charged once.")], "end_turn"),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("app.llm.get_client", return_value=mock_client):
        result = resolve_billing(db_session, customer.id, "Was I charged twice?")

    db_session.refresh(order)
    assert order.status == "processing"  # untouched — no refund tool was called
    assert result.used_tools == ["get_customer_orders"]
    assert result.confidence == 0.6


@patch("app.llm._client", None)
def test_resolve_billing_no_tools_called_is_low_confidence(db_session):
    _seed_billing_scenario(db_session)

    responses = [_response([_text("I'm not sure — could you clarify?")], "end_turn")]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("app.llm.get_client", return_value=mock_client):
        result = resolve_billing(db_session, 1, "something vague")

    assert result.used_tools == []
    assert result.confidence == 0.2
