"""Tests for issue [P6] "Enforce specialist-specific tool permissions".

Proves the permission boundary at BOTH levels the issue requires:

1. Tool exposure — a specialist's tool_schemas (what the LLM is shown)
   contain ONLY its allowed tools. Tests 1-4 check this via
   build_filtered_tool_registry() directly; Test 5 goes one level
   further and inspects the actual kwargs a mocked Anthropic client
   receives through a real resolve_x() call, so this isn't just testing
   the mapping in isolation — it proves the LLM itself would never see
   an unauthorized schema.

2. Tool execution — even if an unauthorized tool_use block reaches the
   loop anyway (a hallucinated name, or a name from a previous
   specialist), it is rejected before the underlying handler runs. Test
   6 proves this by actually exercising call_llm() with a filtered
   registry and confirming the DB is untouched.

Test 7 (existing-behavior regression) is intentionally not duplicated
here — it's `pytest` on the pre-existing suite (test_specialists.py,
test_billing.py, test_order_issues.py, test_tools.py), all of which pass
unmodified (test_order_issues.py needed two one-line call-site updates
for _run_specialist()'s new required `specialist=` kwarg — see that
file). See the PR description / CLAUDE.md for the full verification run.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Customer, KBArticle, Order
from app.llm import call_llm
from app.tools.tool_registry import (
    SPECIALIST_TOOL_PERMISSIONS,
    build_filtered_tool_registry,
)

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
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
    customer = Customer(name="Bob Nunez", email="bob-perm-test@example.com", tier="standard")
    db.add(customer)
    db.flush()
    order = Order(customer_id=customer.id, product="Smart Watch", amount=249.00, status="processing", payment_status="paid")
    db.add(order)
    db.add(KBArticle(title="Refund policy", body="Refunds within 5-7 days.", tags="billing,refund"))
    db.commit()
    db.refresh(order)
    return customer, order


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
# Test 1 — Billing permissions
# ---------------------------------------------------------------------------


def test_billing_receives_all_and_only_its_allowed_tools(db_session):
    expected = {"get_customer", "get_customer_orders", "check_payment_issue", "search_kb", "issue_refund"}
    schemas, handlers = build_filtered_tool_registry(db_session, "billing")

    assert {s["name"] for s in schemas} == expected
    assert set(handlers.keys()) == expected
    assert SPECIALIST_TOOL_PERMISSIONS["billing"] == frozenset(expected)


# ---------------------------------------------------------------------------
# Test 2 — Technical permissions
# ---------------------------------------------------------------------------


def test_technical_does_not_receive_issue_refund(db_session):
    schemas, handlers = build_filtered_tool_registry(db_session, "technical")

    names = {s["name"] for s in schemas}
    assert "issue_refund" not in names
    assert "issue_refund" not in handlers
    # Full expected set, not just the negative check.
    assert names == {"get_customer", "get_customer_tickets", "search_kb"}
    assert set(handlers.keys()) == names


# ---------------------------------------------------------------------------
# Test 3 — Order permissions
# ---------------------------------------------------------------------------


def test_order_does_not_receive_issue_refund(db_session):
    schemas, handlers = build_filtered_tool_registry(db_session, "order")

    names = {s["name"] for s in schemas}
    assert "issue_refund" not in names
    assert "issue_refund" not in handlers
    assert names == {"get_customer", "get_customer_orders", "check_order_issue", "search_kb"}
    assert set(handlers.keys()) == names


# ---------------------------------------------------------------------------
# Test 4 — Account permissions
# ---------------------------------------------------------------------------


def test_account_does_not_receive_issue_refund_or_any_other_mutating_tool(db_session):
    """Account is read-only — get_customer is its ENTIRE allowlist. Explicitly
    checks every other tool in the shared registry (not just issue_refund)
    is absent, since "no mutating tool" is the actual invariant the issue
    cares about, not just the one named example."""
    schemas, handlers = build_filtered_tool_registry(db_session, "account")

    names = {s["name"] for s in schemas}
    assert names == {"get_customer"}
    assert set(handlers.keys()) == {"get_customer"}

    for unauthorized in (
        "issue_refund",
        "check_payment_issue",
        "check_order_issue",
        "get_customer_orders",
        "get_customer_tickets",
        "search_kb",
        "check_room_availability",
    ):
        assert unauthorized not in names
        assert unauthorized not in handlers


# ---------------------------------------------------------------------------
# Test 5 — Tool schemas actually sent to the (mocked) LLM
# ---------------------------------------------------------------------------
# Not enough to test the mapping in isolation — prove the schemas a real
# resolve_x() call hands to Anthropic are already filtered, by inspecting
# the mocked client's own call_args.


@patch("app.llm._client", None)
def test_account_llm_call_never_receives_issue_refund_schema(db_session):
    from app.agents.specialists import resolve_account

    customer = Customer(name="Alice Rao", email="alice-perm-test@example.com", tier="vip")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    responses = [
        _response([_tool_use("t1", "get_customer", {"customer_id": customer.id})], "tool_use"),
        _response([_text("Your account is Alice Rao, VIP tier.")], "end_turn"),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("app.llm.get_client", return_value=mock_client):
        resolve_account(db_session, customer.id, "What's on my account?")

    first_call_kwargs = mock_client.messages.create.call_args_list[0][1]
    sent_tool_names = {t["name"] for t in first_call_kwargs["tools"]}
    assert sent_tool_names == {"get_customer"}
    assert "issue_refund" not in sent_tool_names


@patch("app.llm._client", None)
def test_technical_llm_call_never_receives_issue_refund_schema(db_session):
    from app.agents.specialists import resolve_technical

    customer = Customer(name="Alice Rao", email="alice-tech-perm@example.com", tier="vip")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    responses = [
        _response([_tool_use("t1", "search_kb", {"query": "crash"})], "tool_use"),
        _response([_text("Try clearing your cache.")], "end_turn"),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("app.llm.get_client", return_value=mock_client):
        resolve_technical(db_session, customer.id, "App keeps crashing")

    first_call_kwargs = mock_client.messages.create.call_args_list[0][1]
    sent_tool_names = {t["name"] for t in first_call_kwargs["tools"]}
    assert "issue_refund" not in sent_tool_names
    assert sent_tool_names == {"get_customer", "get_customer_tickets", "search_kb"}


@patch("app.llm._client", None)
def test_order_llm_call_never_receives_issue_refund_schema(db_session):
    from app.agents.specialists import resolve_order

    customer, order = _seed_billing_scenario(db_session)  # reuse: customer + an order

    responses = [
        _response([_tool_use("t1", "get_customer_orders", {"customer_id": customer.id})], "tool_use"),
        _response([_text("Your order is still processing.")], "end_turn"),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("app.llm.get_client", return_value=mock_client):
        resolve_order(db_session, customer.id, "Where is my order?")

    first_call_kwargs = mock_client.messages.create.call_args_list[0][1]
    sent_tool_names = {t["name"] for t in first_call_kwargs["tools"]}
    assert "issue_refund" not in sent_tool_names
    assert sent_tool_names == {"get_customer", "get_customer_orders", "check_order_issue", "search_kb"}


@patch("app.llm._client", None)
def test_billing_llm_call_does_receive_issue_refund_schema(db_session):
    """Contrast case: billing is the one specialist that SHOULD see it."""
    from app.agents.specialists import resolve_billing

    customer, order = _seed_billing_scenario(db_session)

    responses = [
        _response([_tool_use("t1", "get_customer_orders", {"customer_id": customer.id})], "tool_use"),
        _response([_text("Let me check that for you.")], "end_turn"),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("app.llm.get_client", return_value=mock_client):
        resolve_billing(db_session, customer.id, "Was I charged twice?")

    first_call_kwargs = mock_client.messages.create.call_args_list[0][1]
    sent_tool_names = {t["name"] for t in first_call_kwargs["tools"]}
    assert "issue_refund" in sent_tool_names


# ---------------------------------------------------------------------------
# Test 6 — Defensive execution: an unauthorized tool_use must be rejected,
# not executed, even if it reaches the tool-calling loop.
# ---------------------------------------------------------------------------


@patch("app.llm._client", None)
def test_unauthorized_tool_call_is_rejected_not_executed(db_session):
    """Simulates a model that (whether hallucinating, jailbroken, or just
    buggy) emits a tool_use block for `issue_refund` despite the Account
    specialist never having been shown that schema. Proves all three
    required properties: the tool is NOT executed, the database is
    unchanged, and a deterministic error is returned — and that this is
    real code behavior, not a text assertion, by using the ACTUAL
    filtered registry + the ACTUAL call_llm() tool loop, with a real
    seeded order that mock_tools.issue_refund could otherwise refund.
    """
    customer, order = _seed_billing_scenario(db_session)
    assert order.status == "processing"  # sanity check before the attempt

    account_schemas, account_handlers = build_filtered_tool_registry(db_session, "account")
    assert "issue_refund" not in account_handlers  # pre-condition for this test to mean anything

    unauthorized_attempt = _tool_use("tu_bad", "issue_refund", {"order_id": order.id})
    final_reply = _text("I'm not able to process that here.")

    responses = [
        _response([unauthorized_attempt], "tool_use"),
        _response([final_reply], "end_turn"),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    used_tools: list[str] = []
    with patch("app.llm.get_client", return_value=mock_client):
        result = call_llm(
            system_prompt="You are the Account specialist.",
            messages=[{"role": "user", "content": "Please refund my order."}],
            tools=(account_schemas, account_handlers),
            tool_call_log=used_tools,
        )

    # 1. The loop still completed gracefully (didn't crash) and returned the
    #    model's follow-up text rather than raising.
    assert result == "I'm not able to process that here."

    # 2. The tool was NOT executed — the database is unchanged.
    db_session.refresh(order)
    assert order.status == "processing"
    assert order.payment_status == "paid"

    # 3. A deterministic permission-shaped error was returned to the model,
    #    not a silent no-op — the second Anthropic call's tool_result is
    #    marked as an error and names the rejected tool.
    second_call_kwargs = mock_client.messages.create.call_args_list[1][1]
    tool_result = next(
        b for b in second_call_kwargs["messages"][-1]["content"] if b.get("type") == "tool_result"
    )
    assert tool_result["is_error"] is True
    assert "issue_refund" in tool_result["content"]

    # 4. The attempt is still visible in the trace log — a rejected attempt
    #    is recorded, not silently dropped, so it's auditable even though it
    #    never ran.
    assert used_tools == ["issue_refund"]


@patch("app.llm._client", None)
def test_unauthorized_tool_would_have_worked_if_authorized_control_case(db_session):
    """Control case for the test above: the SAME tool_use block, against
    the BILLING registry (which is authorized), actually executes and
    changes the database — proving the rejection above is really caused
    by the permission filter, not by some unrelated reason (a broken
    handler, a bad order id, etc.)."""
    customer, order = _seed_billing_scenario(db_session)

    billing_schemas, billing_handlers = build_filtered_tool_registry(db_session, "billing")
    assert "issue_refund" in billing_handlers

    responses = [
        _response([_tool_use("tu_ok", "issue_refund", {"order_id": order.id})], "tool_use"),
        _response([_text("Refunded.")], "end_turn"),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("app.llm.get_client", return_value=mock_client):
        result = call_llm(
            system_prompt="You are the Billing specialist.",
            messages=[{"role": "user", "content": "Please refund my order."}],
            tools=(billing_schemas, billing_handlers),
        )

    assert result == "Refunded."
    db_session.refresh(order)
    assert order.status == "refunded"


# ---------------------------------------------------------------------------
# Unknown specialist key — programming-error guard, not an LLM-facing check
# ---------------------------------------------------------------------------


def test_build_filtered_tool_registry_rejects_unknown_specialist(db_session):
    with pytest.raises(ValueError, match="Unknown specialist"):
        build_filtered_tool_registry(db_session, "not_a_real_specialist")
