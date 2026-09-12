"""Network-free tests for Issue #5 — LLM tool-calling infrastructure.

Tests cover:
  A. Tool schema registration
  B. Tool execution via the registry
  C. Tool result serialization
  D. LLM tool-calling loop (Anthropic client fully mocked)
  E. Multiple tool calls in one LLM response
  F. Maximum iteration protection
  G. Backward compatibility with existing call_llm() callers
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.db.models import Customer, KBArticle, Order, Room, Ticket
from app.llm import LLMError, call_llm
from app.tools.tool_registry import (
    TOOL_NAMES,
    TOOL_SCHEMAS,
    build_tool_registry,
    serialize_tool_result,
)

# ---------------------------------------------------------------------------
# Helpers — build stubs that pass isinstance() checks in _serialize()
# ---------------------------------------------------------------------------
# Use spec= so isinstance(obj, Order) etc. return True inside _serialize().

def _order(id=1, customer_id=1, product="Smart Watch", amount=199.99,
           status="shipped", created_at=None):
    o = MagicMock(spec=Order)
    o.id = id
    o.customer_id = customer_id
    o.product = product
    o.amount = amount
    o.status = status
    o.created_at = created_at or datetime(2024, 1, 15, 10, 0, 0)
    return o


def _customer(id=1, name="Alice", email="alice@example.com",
              phone="555-0001", tier="vip"):
    c = MagicMock(spec=Customer)
    c.id = id
    c.name = name
    c.email = email
    c.phone = phone
    c.tier = tier
    return c



def _ticket(id=10, customer_id=1, category="order", subject="Late delivery",
            message="Where is my order?", sentiment="negative",
            urgency=7, status="open", created_at=None):
    t = MagicMock(spec=Ticket)
    t.id = id
    t.customer_id = customer_id
    t.category = category
    t.subject = subject
    t.message = message
    t.sentiment = sentiment
    t.urgency = urgency
    t.status = status
    t.created_at = created_at or datetime(2024, 1, 10, 9, 0, 0)
    return t


def _kb_article(id=5, title="Refund Policy", body="You may refund within 30 days.",
                tags="refund,policy"):
    a = MagicMock(spec=KBArticle)
    a.id = id
    a.title = title
    a.body = body
    a.tags = tags
    return a


def _room(id=2, room_type="deluxe", price_per_night=150.0, total_count=10):
    r = MagicMock(spec=Room)
    r.id = id
    r.room_type = room_type
    r.price_per_night = price_per_night
    r.total_count = total_count
    return r


# ---------------------------------------------------------------------------
# A. Tool schema registration
# ---------------------------------------------------------------------------

EXPECTED_TOOL_NAMES = {
    "get_customer",
    "get_customer_orders",
    "get_customer_tickets",
    "search_kb",
    "issue_refund",
    "check_room_availability",
}


def test_all_six_tools_are_registered():
    assert TOOL_NAMES == EXPECTED_TOOL_NAMES


def test_tool_schemas_have_stable_names():
    schema_names = {s["name"] for s in TOOL_SCHEMAS}
    assert schema_names == EXPECTED_TOOL_NAMES


def test_get_customer_orders_schema_requires_customer_id():
    schema = next(s for s in TOOL_SCHEMAS if s["name"] == "get_customer_orders")
    required = schema["input_schema"].get("required", [])
    assert "customer_id" in required
    props = schema["input_schema"]["properties"]
    assert "customer_id" in props
    assert props["customer_id"]["type"] == "integer"


def test_issue_refund_schema_requires_order_id():
    schema = next(s for s in TOOL_SCHEMAS if s["name"] == "issue_refund")
    required = schema["input_schema"].get("required", [])
    assert "order_id" in required


def test_search_kb_schema_requires_query():
    schema = next(s for s in TOOL_SCHEMAS if s["name"] == "search_kb")
    required = schema["input_schema"].get("required", [])
    assert "query" in required


def test_check_room_availability_schema_requires_room_type():
    schema = next(s for s in TOOL_SCHEMAS if s["name"] == "check_room_availability")
    required = schema["input_schema"].get("required", [])
    assert "room_type" in required


def test_every_schema_has_description():
    for s in TOOL_SCHEMAS:
        assert s.get("description"), f"{s['name']} is missing a description"


def test_every_schema_has_input_schema():
    for s in TOOL_SCHEMAS:
        assert "input_schema" in s, f"{s['name']} is missing input_schema"
        assert s["input_schema"].get("type") == "object"


# ---------------------------------------------------------------------------
# B. Tool execution via build_tool_registry
# ---------------------------------------------------------------------------

def test_get_customer_orders_handler_passes_customer_id():
    db = MagicMock()
    orders = [_order()]
    with patch("app.tools.mock_tools.get_customer_orders", return_value=orders) as mock_fn:
        _, handlers = build_tool_registry(db)
        result = handlers["get_customer_orders"]({"customer_id": 42})
        mock_fn.assert_called_once_with(db, 42)
        assert result == orders


def test_get_customer_handler_passes_customer_id():
    db = MagicMock()
    customer = _customer()
    with patch("app.tools.mock_tools.get_customer", return_value=customer) as mock_fn:
        _, handlers = build_tool_registry(db)
        handlers["get_customer"]({"customer_id": 1})
        mock_fn.assert_called_once_with(db, 1)


def test_get_customer_tickets_handler_passes_customer_id():
    db = MagicMock()
    with patch("app.tools.mock_tools.get_customer_tickets", return_value=[]) as mock_fn:
        _, handlers = build_tool_registry(db)
        handlers["get_customer_tickets"]({"customer_id": 7})
        mock_fn.assert_called_once_with(db, 7)


def test_search_kb_handler_passes_query():
    db = MagicMock()
    with patch("app.tools.mock_tools.search_kb", return_value=[]) as mock_fn:
        _, handlers = build_tool_registry(db)
        handlers["search_kb"]({"query": "refund"})
        mock_fn.assert_called_once_with(db, "refund")


def test_issue_refund_handler_passes_order_id():
    db = MagicMock()
    order = _order(status="refunded")
    with patch("app.tools.mock_tools.issue_refund", return_value=order) as mock_fn:
        _, handlers = build_tool_registry(db)
        handlers["issue_refund"]({"order_id": 99})
        mock_fn.assert_called_once_with(db, 99)


def test_check_room_availability_handler_passes_room_type():
    db = MagicMock()
    with patch("app.tools.mock_tools.check_room_availability", return_value=None) as mock_fn:
        _, handlers = build_tool_registry(db)
        handlers["check_room_availability"]({"room_type": "suite"})
        mock_fn.assert_called_once_with(db, "suite")


# ---------------------------------------------------------------------------
# C. Tool result serialization
# ---------------------------------------------------------------------------

def test_serialize_none():
    assert json.loads(serialize_tool_result(None)) is None


def test_serialize_single_order_preserves_fields():
    order = _order(id=5, product="Laptop", amount=999.0, status="delivered")
    data = json.loads(serialize_tool_result(order))
    assert data["id"] == 5
    assert data["product"] == "Laptop"
    assert data["amount"] == 999.0
    assert data["status"] == "delivered"
    assert "customer_id" in data
    assert "created_at" in data


def test_serialize_order_list():
    orders = [_order(id=1, status="shipped"), _order(id=2, status="delivered")]
    data = json.loads(serialize_tool_result(orders))
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["id"] == 1
    assert data[1]["id"] == 2


def test_serialize_customer():
    c = _customer(name="Bob", email="bob@example.com", tier="standard")
    data = json.loads(serialize_tool_result(c))
    assert data["name"] == "Bob"
    assert data["email"] == "bob@example.com"
    assert data["tier"] == "standard"


def test_serialize_ticket():
    t = _ticket(subject="Missing item", urgency=8, status="open")
    data = json.loads(serialize_tool_result(t))
    assert data["subject"] == "Missing item"
    assert data["urgency"] == 8
    assert data["status"] == "open"


def test_serialize_kb_article():
    a = _kb_article(title="Shipping Info", body="Ships in 3-5 days.")
    data = json.loads(serialize_tool_result(a))
    assert data["title"] == "Shipping Info"
    assert data["body"] == "Ships in 3-5 days."


def test_serialize_room():
    r = _room(room_type="suite", price_per_night=300.0, total_count=3)
    data = json.loads(serialize_tool_result(r))
    assert data["room_type"] == "suite"
    assert data["price_per_night"] == 300.0


def test_serialize_does_not_contain_sqlalchemy_state():
    """Serialized result must not contain SQLAlchemy internals."""
    order = _order()
    result_str = serialize_tool_result(order)
    assert "_sa_instance_state" not in result_str
    assert "sqlalchemy" not in result_str.lower()


def test_serialize_result_is_valid_json():
    orders = [_order(id=i) for i in range(3)]
    result_str = serialize_tool_result(orders)
    # Must not raise
    parsed = json.loads(result_str)
    assert isinstance(parsed, list)


# ---------------------------------------------------------------------------
# D. LLM tool-calling loop (Anthropic client mocked)
# ---------------------------------------------------------------------------

def _make_tool_use_block(id: str, name: str, input_: dict):
    """Build a mock ToolUseBlock with the minimum fields call_llm() reads."""
    block = MagicMock()
    block.type = "tool_use"
    block.id = id
    block.name = name
    block.input = input_
    return block


def _make_text_block(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_response(content: list, stop_reason: str = "tool_use"):
    resp = MagicMock()
    resp.content = content
    resp.stop_reason = stop_reason
    return resp


def _make_handlers(tool_name: str, return_value: Any) -> dict:
    return {tool_name: MagicMock(return_value=return_value)}


@patch("app.llm._client", None)
def test_tool_loop_single_tool_call(monkeypatch):
    """Verify the happy-path tool-calling loop:
    1st call → tool_use, 2nd call → end_turn with text.
    """
    orders = [_order(id=7, status="shipped")]
    tool_block = _make_tool_use_block("tu_001", "get_customer_orders", {"customer_id": 1})
    text_block = _make_text_block("Your order is shipped.")

    first_response = _make_response([tool_block], stop_reason="tool_use")
    second_response = _make_response([text_block], stop_reason="end_turn")

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [first_response, second_response]

    with patch("app.llm.get_client", return_value=mock_client):
        handler = MagicMock(return_value=orders)
        schemas = [TOOL_SCHEMAS[1]]  # get_customer_orders
        handlers = {"get_customer_orders": handler}

        result = call_llm(
            system_prompt="You are a helpful support agent.",
            messages=[{"role": "user", "content": "Where is my order?"}],
            tools=(schemas, handlers),
        )

    assert result == "Your order is shipped."

    # Anthropic called twice
    assert mock_client.messages.create.call_count == 2

    # Handler was called with the correct args
    handler.assert_called_once_with({"customer_id": 1})

    # Second call includes a tool_result message with the correct tool_use_id
    second_call_messages = mock_client.messages.create.call_args_list[1][1]["messages"]
    tool_result_msg = second_call_messages[-1]
    assert tool_result_msg["role"] == "user"
    assert any(
        block.get("tool_use_id") == "tu_001"
        for block in tool_result_msg["content"]
    )


@patch("app.llm._client", None)
def test_tool_loop_result_json_in_tool_result(monkeypatch):
    """Verify the tool_result content is valid JSON with order fields."""
    order = _order(id=99, status="delivered")
    tool_block = _make_tool_use_block("tu_002", "get_customer_orders", {"customer_id": 2})
    text_block = _make_text_block("Order 99 is delivered.")

    first_response = _make_response([tool_block], stop_reason="tool_use")
    second_response = _make_response([text_block], stop_reason="end_turn")

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [first_response, second_response]

    captured_messages = []

    def capture_create(**kwargs):
        captured_messages.append(kwargs["messages"])
        return mock_client.messages.create.side_effect.pop(0) if isinstance(
            mock_client.messages.create.side_effect, list
        ) else None

    with patch("app.llm.get_client", return_value=mock_client):
        handlers = {"get_customer_orders": MagicMock(return_value=[order])}
        call_llm(
            system_prompt="Agent",
            messages=[{"role": "user", "content": "order status?"}],
            tools=([TOOL_SCHEMAS[1]], handlers),
        )

    # Find the tool_result in the second Anthropic call
    second_call_kwargs = mock_client.messages.create.call_args_list[1][1]
    user_msg = second_call_kwargs["messages"][-1]
    tool_result_blocks = [b for b in user_msg["content"] if b.get("type") == "tool_result"]
    assert len(tool_result_blocks) == 1

    content_json = json.loads(tool_result_blocks[0]["content"])
    assert isinstance(content_json, list)
    assert content_json[0]["id"] == 99
    assert content_json[0]["status"] == "delivered"


# ---------------------------------------------------------------------------
# E. Multiple tool calls in a single LLM response
# ---------------------------------------------------------------------------

@patch("app.llm._client", None)
def test_tool_loop_multiple_tools_in_one_response():
    """Both tools in one response are executed and both tool_results returned."""
    tool_block_1 = _make_tool_use_block("tu_a", "get_customer", {"customer_id": 1})
    tool_block_2 = _make_tool_use_block("tu_b", "get_customer_orders", {"customer_id": 1})
    text_block = _make_text_block("Done.")

    first_response = _make_response([tool_block_1, tool_block_2], stop_reason="tool_use")
    second_response = _make_response([text_block], stop_reason="end_turn")

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [first_response, second_response]

    handler_customer = MagicMock(return_value=_customer())
    handler_orders = MagicMock(return_value=[_order()])

    with patch("app.llm.get_client", return_value=mock_client):
        schemas = [TOOL_SCHEMAS[0], TOOL_SCHEMAS[1]]
        handlers = {
            "get_customer": handler_customer,
            "get_customer_orders": handler_orders,
        }
        result = call_llm(
            system_prompt="Agent",
            messages=[{"role": "user", "content": "Tell me about my account."}],
            tools=(schemas, handlers),
        )

    assert result == "Done."
    handler_customer.assert_called_once_with({"customer_id": 1})
    handler_orders.assert_called_once_with({"customer_id": 1})

    # Both tool_results are in the second Anthropic call
    second_call_kwargs = mock_client.messages.create.call_args_list[1][1]
    user_msg = second_call_kwargs["messages"][-1]
    result_ids = {b["tool_use_id"] for b in user_msg["content"] if b.get("type") == "tool_result"}
    assert result_ids == {"tu_a", "tu_b"}


# ---------------------------------------------------------------------------
# F. Unknown tool name and tool execution error handling
# ---------------------------------------------------------------------------

@patch("app.llm._client", None)
def test_unknown_tool_name_returns_error_result_not_crash():
    """An unknown tool name must be reported back to the model, not crash."""
    unknown_block = _make_tool_use_block("tu_x", "nonexistent_tool", {})
    text_block = _make_text_block("I cannot help with that.")

    first_response = _make_response([unknown_block], stop_reason="tool_use")
    second_response = _make_response([text_block], stop_reason="end_turn")

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [first_response, second_response]

    with patch("app.llm.get_client", return_value=mock_client):
        result = call_llm(
            system_prompt="Agent",
            messages=[{"role": "user", "content": "test"}],
            tools=([TOOL_SCHEMAS[0]], {}),  # empty handlers — nothing registered
        )

    assert result == "I cannot help with that."

    # The tool_result must be marked as an error
    second_call_kwargs = mock_client.messages.create.call_args_list[1][1]
    user_msg = second_call_kwargs["messages"][-1]
    err_block = next(b for b in user_msg["content"] if b.get("type") == "tool_result")
    assert err_block.get("is_error") is True
    assert "nonexistent_tool" in err_block["content"]


@patch("app.llm._client", None)
def test_tool_exception_returns_error_result_not_crash():
    """Exceptions raised by a tool handler must not propagate to the caller."""
    tool_block = _make_tool_use_block("tu_err", "get_customer_orders", {"customer_id": 1})
    text_block = _make_text_block("An error occurred.")

    first_response = _make_response([tool_block], stop_reason="tool_use")
    second_response = _make_response([text_block], stop_reason="end_turn")

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [first_response, second_response]

    exploding_handler = MagicMock(side_effect=RuntimeError("DB connection lost"))

    with patch("app.llm.get_client", return_value=mock_client):
        result = call_llm(
            system_prompt="Agent",
            messages=[{"role": "user", "content": "test"}],
            tools=([TOOL_SCHEMAS[1]], {"get_customer_orders": exploding_handler}),
        )

    assert result == "An error occurred."
    second_call_kwargs = mock_client.messages.create.call_args_list[1][1]
    user_msg = second_call_kwargs["messages"][-1]
    err_block = next(b for b in user_msg["content"] if b.get("type") == "tool_result")
    assert err_block.get("is_error") is True
    assert "DB connection lost" in err_block["content"]


# ---------------------------------------------------------------------------
# F. Maximum loop protection
# ---------------------------------------------------------------------------

@patch("app.llm._client", None)
def test_max_tool_iterations_raises_llm_error():
    """If the model keeps requesting tools without a final answer, LLMError is raised."""
    from app.llm import _MAX_TOOL_ITERATIONS

    tool_block = _make_tool_use_block("tu_inf", "get_customer_orders", {"customer_id": 1})
    infinite_response = _make_response([tool_block], stop_reason="tool_use")

    mock_client = MagicMock()
    # Always return a tool_use response — should hit the limit
    mock_client.messages.create.return_value = infinite_response

    handler = MagicMock(return_value=[])

    with patch("app.llm.get_client", return_value=mock_client):
        with pytest.raises(LLMError, match="exceeded"):
            call_llm(
                system_prompt="Agent",
                messages=[{"role": "user", "content": "loop forever"}],
                tools=([TOOL_SCHEMAS[1]], {"get_customer_orders": handler}),
            )

    assert mock_client.messages.create.call_count == _MAX_TOOL_ITERATIONS


# ---------------------------------------------------------------------------
# G. Backward compatibility — existing callers must work unchanged
# ---------------------------------------------------------------------------

def test_call_llm_plain_text_no_tools(monkeypatch):
    """call_llm with no tools arg must return plain text as before."""
    text_block = _make_text_block("Hello!")
    resp = _make_response([text_block], stop_reason="end_turn")

    mock_client = MagicMock()
    mock_client.messages.create.return_value = resp

    with patch("app.llm.get_client", return_value=mock_client):
        result = call_llm("You are helpful.", [{"role": "user", "content": "Hi"}])

    assert result == "Hello!"
    # No 'tools' key in the call kwargs when tools=None
    call_kwargs = mock_client.messages.create.call_args[1]
    assert "tools" not in call_kwargs


def test_call_llm_structured_output_no_tools(monkeypatch):
    """response_schema path must still work (uses messages.parse, not create)."""
    from pydantic import BaseModel

    class _Schema(BaseModel):
        value: str

    parsed_obj = _Schema(value="ok")
    mock_parsed = MagicMock()
    mock_parsed.parsed_output = parsed_obj

    mock_client = MagicMock()
    mock_client.messages.parse.return_value = mock_parsed

    with patch("app.llm.get_client", return_value=mock_client):
        result = call_llm(
            "System.",
            [{"role": "user", "content": "test"}],
            response_schema=_Schema,
        )

    assert result.value == "ok"
    mock_client.messages.parse.assert_called_once()
    mock_client.messages.create.assert_not_called()


def test_llm_error_is_a_runtime_error():
    assert issubclass(LLMError, RuntimeError)


def test_get_client_constructs_without_network_call():
    from app.llm import get_client
    # Patch _client to None to force reconstruction, but mock Anthropic so no
    # real connection is attempted.
    with patch("app.llm._client", None):
        with patch("app.llm.anthropic.Anthropic") as mock_cls:
            mock_cls.return_value = MagicMock()
            client = get_client()
            assert client is not None
