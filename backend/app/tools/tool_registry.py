"""Tool registry for LLM tool-calling. Implements issue #5
"[P0] Real tool-calling: give specialist agents actual LLM tool-call access".

This module owns three concerns:

1. Anthropic-compatible tool schemas (ToolParam dicts) for every function in
   app/tools/mock_tools.py.

2. Safe serialization of SQLAlchemy model results into plain dicts that can
   be embedded in an Anthropic tool_result message.

3. A factory (build_tool_registry) that wires a live database Session into
   each handler so specialist agents never have to import the SDK or the DB
   directly. Everything database-related stays here.

Usage by a specialist:

    from app.tools.tool_registry import build_tool_registry
    from app.llm import call_llm

    tool_schemas, tool_handlers = build_tool_registry(db)
    answer = call_llm(
        system_prompt=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": message}],
        tools=(tool_schemas, tool_handlers),
    )
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.db.models import Customer, KBArticle, Order, Room, Ticket
from app.tools import mock_tools

# ---------------------------------------------------------------------------
# Serialization — never pass raw SQLAlchemy objects into LLM messages
# ---------------------------------------------------------------------------

def _serialize(obj: Any) -> Any:
    """Recursively convert SQLAlchemy model instances and lists to plain dicts.

    Keeps only scalar fields (strings, ints, floats) so no lazy-load is
    accidentally triggered and no internal SQLAlchemy state leaks into the
    Anthropic message payload.
    """
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_serialize(item) for item in obj]
    if isinstance(obj, Customer):
        return {
            "id": obj.id,
            "name": obj.name,
            "email": obj.email,
            "phone": obj.phone,
            "tier": obj.tier,
        }
    if isinstance(obj, Order):
        return {
            "id": obj.id,
            "customer_id": obj.customer_id,
            "product": obj.product,
            "amount": obj.amount,
            "status": obj.status,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
        }
    if isinstance(obj, Ticket):
        return {
            "id": obj.id,
            "customer_id": obj.customer_id,
            "category": obj.category,
            "subject": obj.subject,
            "message": obj.message,
            "sentiment": obj.sentiment,
            "urgency": obj.urgency,
            "status": obj.status,
            "created_at": obj.created_at.isoformat() if obj.created_at else None,
        }
    if isinstance(obj, KBArticle):
        return {
            "id": obj.id,
            "title": obj.title,
            "body": obj.body,
            "tags": obj.tags,
        }
    if isinstance(obj, Room):
        return {
            "id": obj.id,
            "room_type": obj.room_type,
            "price_per_night": obj.price_per_night,
            "total_count": obj.total_count,
        }
    # Scalar fallback — already JSON-safe
    return obj


def serialize_tool_result(result: Any) -> str:
    """Return a JSON string suitable for embedding in a tool_result message."""
    return json.dumps(_serialize(result), default=str)


# ---------------------------------------------------------------------------
# Tool definitions — Anthropic ToolParam dicts
# ---------------------------------------------------------------------------

#: Stable list of all tool schemas exposed to the LLM.
TOOL_SCHEMAS: list[dict] = [
    {
        "name": "get_customer",
        "description": (
            "Retrieve the customer profile (name, email, phone, tier) for a given "
            "customer ID. Call this first to confirm the customer exists and learn "
            "their tier (standard vs. vip) before looking up orders or tickets."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "integer",
                    "description": "The unique numeric ID of the customer.",
                }
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "get_customer_orders",
        "description": (
            "Return the list of orders placed by a customer, including product name, "
            "amount, status (processing / shipped / delivered / refunded), and "
            "creation date. Use this to answer questions about order status, "
            "delivery, or purchase history."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "integer",
                    "description": "The unique numeric ID of the customer whose orders to fetch.",
                }
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "get_customer_tickets",
        "description": (
            "Return all support tickets filed by a customer (category, subject, "
            "message, urgency, status). Useful for understanding the customer's "
            "support history before responding to a new issue."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "integer",
                    "description": "The unique numeric ID of the customer whose tickets to fetch.",
                }
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "search_kb",
        "description": (
            "Search the knowledge base for articles relevant to the customer's "
            "question. Pass a short keyword query (e.g. 'refund policy', "
            "'shipping delay'). Returns matching articles with title, body, and tags."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keyword query to match against KB article titles, bodies, and tags.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "check_payment_issue",
        "description": (
            "Check an order for payment anomalies, such as duplicate charges or payment/fulfillment mismatches. "
            "Call this BEFORE deciding to refund an order."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "integer",
                    "description": "The unique numeric ID of the order to check.",
                }
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "issue_refund",
        "description": (
            "Mark an order as refunded in the database. Only call this after you "
            "have confirmed with the customer that a refund is appropriate and you "
            "know the exact order ID. Returns the updated order record."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "integer",
                    "description": "The unique numeric ID of the order to refund.",
                }
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "check_room_availability",
        "description": (
            "Check whether a hotel room of a given type is available (stretch "
            "feature). Returns room details including price per night and total "
            "count. Room types are: standard, deluxe, suite."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "room_type": {
                    "type": "string",
                    "description": "The room category to check: standard, deluxe, or suite.",
                }
            },
            "required": ["room_type"],
        },
    },
]

#: Stable set of all exposed tool names, for fast membership testing.
TOOL_NAMES: frozenset[str] = frozenset(s["name"] for s in TOOL_SCHEMAS)


# ---------------------------------------------------------------------------
# Registry factory — binds a live DB session into every handler
# ---------------------------------------------------------------------------

@dataclass
class _BoundTool:
    """Internal: one tool schema + its session-bound callable."""
    schema: dict
    handler: Callable[..., Any]


def build_tool_registry(
    db: Session,
) -> tuple[list[dict], dict[str, Callable[..., Any]]]:
    """Return ``(tool_schemas, tool_handlers)`` with ``db`` already bound.

    ``tool_schemas``  — list of Anthropic ToolParam dicts, ready to pass to
                        ``call_llm(..., tools=(tool_schemas, tool_handlers))``.
    ``tool_handlers`` — dict mapping tool name → callable(input_args: dict) -> Any.
                        Each callable returns a raw Python value; ``call_llm``
                        will call ``serialize_tool_result`` on it before feeding
                        the result back to the model.
    """
    bound: list[_BoundTool] = [
        _BoundTool(
            schema=TOOL_SCHEMAS[0],  # get_customer
            handler=lambda args: mock_tools.get_customer(db, args["customer_id"]),
        ),
        _BoundTool(
            schema=TOOL_SCHEMAS[1],  # get_customer_orders
            handler=lambda args: mock_tools.get_customer_orders(db, args["customer_id"]),
        ),
        _BoundTool(
            schema=TOOL_SCHEMAS[2],  # get_customer_tickets
            handler=lambda args: mock_tools.get_customer_tickets(db, args["customer_id"]),
        ),
        _BoundTool(
            schema=TOOL_SCHEMAS[3],  # search_kb
            handler=lambda args: mock_tools.search_kb(db, args["query"]),
        ),
        _BoundTool(
            schema=TOOL_SCHEMAS[4],  # check_payment_issue
            handler=lambda args: mock_tools.check_payment_issue(db, args["order_id"]),
        ),
        _BoundTool(
            schema=TOOL_SCHEMAS[5],  # issue_refund
            handler=lambda args: mock_tools.issue_refund(db, args["order_id"]),
        ),
        _BoundTool(
            schema=TOOL_SCHEMAS[6],  # check_room_availability
            handler=lambda args: mock_tools.check_room_availability(db, args["room_type"]),
        ),
    ]

    schemas = [b.schema for b in bound]
    handlers = {b.schema["name"]: b.handler for b in bound}
    return schemas, handlers
