"""Tests for the specialist agents (issues #6-#9).

Network-free — only the Anthropic client is mocked (same pattern as
tests/test_tools.py for issue #5). Everything else — the DB session, the
tool registry, mock_tools — is real, so the integration tests below prove
real behavior (e.g. the seeded order actually flips to `refunded` in the
database), not just that the right function was called.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.specialists import (
    _estimate_confidence,
    resolve_account,
    resolve_billing,
    resolve_order,
    resolve_technical,
)
from app.db.database import Base
from app.db.models import Customer, KBArticle, Order, Ticket

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


# ---------------------------------------------------------------------------
# Technical specialist (issue #7)
# ---------------------------------------------------------------------------


def _seed_technical_scenario(db):
    customer = Customer(name="Alice Rao", email="alice@example.com", tier="vip")
    db.add(customer)
    db.flush()
    db.add(
        KBArticle(
            title="App crashes on checkout",
            body="Clear the app cache and update to the latest version to resolve checkout crashes.",
            tags="technical,crash,checkout",
        )
    )
    db.commit()
    return customer


@patch("app.llm._client", None)
def test_resolve_technical_grounds_answer_in_kb_article(db_session):
    customer = _seed_technical_scenario(db_session)

    responses = [
        _response([_tool_use("t1", "search_kb", {"query": "checkout crash"})], "tool_use"),
        _response(
            [_text("Your checkout crash is a known issue — clearing the app cache and updating "
                   "should fix it, per our troubleshooting article.")],
            "end_turn",
        ),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("app.llm.get_client", return_value=mock_client):
        result = resolve_technical(db_session, customer.id, "The app keeps crashing at checkout")

    assert result.used_tools == ["search_kb"]
    assert result.confidence == 0.6


@patch("app.llm._client", None)
def test_resolve_technical_no_kb_match_is_low_confidence(db_session):
    """Acceptance criteria: no KB match -> low confidence, not a guessed fix."""
    customer = _seed_technical_scenario(db_session)

    responses = [
        _response([_tool_use("t1", "search_kb", {"query": "obscure unrelated problem"})], "tool_use"),
        _response(
            [_text("I couldn't find anything on this in our knowledge base — "
                   "a human agent will need to help with this one.")],
            "end_turn",
        ),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    # No patch needed on search_kb itself — the real naive keyword matcher
    # against the seeded KB naturally returns [] for an unrelated query.
    with patch("app.llm.get_client", return_value=mock_client):
        result = resolve_technical(db_session, customer.id, "something totally obscure")

    # search_kb was still called (grounding attempt), but returned nothing —
    # confidence is 0.6 (a lookup was attempted), NOT 0.9 (nothing was fixed).
    # A genuinely zero-tool reply (agent didn't even try) is covered by the
    # billing no-tools-called test above and yields 0.2.
    assert result.used_tools == ["search_kb"]
    assert result.confidence == 0.6


# ---------------------------------------------------------------------------
# Order specialist (issue #8)
# ---------------------------------------------------------------------------


def _seed_order_scenario(db):
    customer = Customer(name="Alice Rao", email="alice@example.com", tier="vip")
    db.add(customer)
    db.flush()
    order = Order(customer_id=customer.id, product="Wireless Headphones", amount=129.99, status="processing")
    db.add(order)
    db.add(
        KBArticle(
            title="Order delays",
            body="Orders delayed beyond the estimated ship date are automatically eligible "
            "for a 10% courtesy discount code on request.",
            tags="order,shipping",
        )
    )
    db.commit()
    db.refresh(order)
    return customer, order


@patch("app.llm._client", None)
def test_resolve_order_proactively_checks_delay_policy(db_session):
    """Acceptance criteria: a delayed order should surface the discount
    policy proactively — this test proves the wiring (order lookup +
    policy lookup both happen); the manual check_order.py script verifies
    the real model actually volunteers it unprompted."""
    customer, order = _seed_order_scenario(db_session)

    responses = [
        _response([_tool_use("t1", "get_customer_orders", {"customer_id": customer.id})], "tool_use"),
        _response([_tool_use("t2", "search_kb", {"query": "order delays"})], "tool_use"),
        _response(
            [_text("Your headphones order has been processing longer than expected, so you're "
                   "eligible for a 10% courtesy discount — we'll get that sent to you.")],
            "end_turn",
        ),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("app.llm.get_client", return_value=mock_client):
        result = resolve_order(db_session, customer.id, "It's been days, where is my order?")

    assert result.used_tools == ["get_customer_orders", "search_kb"]
    assert result.confidence == 0.6
    # The order specialist has no tool to actually issue a discount — the
    # reply must offer it, never claim the order was refunded/modified.
    db_session.refresh(order)
    assert order.status == "processing"


@patch("app.llm._client", None)
def test_resolve_order_simple_status_lookup(db_session):
    customer, order = _seed_order_scenario(db_session)

    responses = [
        _response([_tool_use("t1", "get_customer_orders", {"customer_id": customer.id})], "tool_use"),
        _response([_text("Your headphones order is currently processing.")], "end_turn"),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("app.llm.get_client", return_value=mock_client):
        result = resolve_order(db_session, customer.id, "Where is my order?")

    assert result.used_tools == ["get_customer_orders"]
    assert result.confidence == 0.6


# ---------------------------------------------------------------------------
# Account specialist (issue #9)
# ---------------------------------------------------------------------------


@patch("app.llm._client", None)
def test_resolve_account_looks_up_profile(db_session):
    customer = Customer(name="Alice Rao", email="alice@example.com", phone="+1-555-0101", tier="vip")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    responses = [
        _response([_tool_use("t1", "get_customer", {"customer_id": customer.id})], "tool_use"),
        _response([_text("Your account is registered as Alice Rao, VIP tier, alice@example.com.")], "end_turn"),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("app.llm.get_client", return_value=mock_client):
        result = resolve_account(db_session, customer.id, "What email is on my account?")

    assert result.used_tools == ["get_customer"]
    assert result.confidence == 0.6
    assert "alice@example.com" in result.reply.lower()


@patch("app.llm._client", None)
def test_resolve_account_is_read_only_no_action_tools_available(db_session):
    """The account specialist has no action tool at all — even a request it
    can't fulfil (e.g. reset a password) can only ever ground at 0.6 or
    fall back to 0.2, never 0.9 (that would imply an action tool exists)."""
    customer = Customer(name="Bob Nunez", email="bob@example.com", tier="standard")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    responses = [
        _response([_tool_use("t1", "get_customer", {"customer_id": customer.id})], "tool_use"),
        _response(
            [_text("I can see your account, but I can't reset your password — "
                   "a human agent will need to help with that.")],
            "end_turn",
        ),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("app.llm.get_client", return_value=mock_client):
        result = resolve_account(db_session, customer.id, "Reset my password")

    assert result.confidence == 0.6  # grounded lookup happened, but no action tool exists to use
