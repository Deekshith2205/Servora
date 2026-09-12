"""Tool registry for LLM tool-calling. Implements issue #5
"[P0] Real tool-calling: give specialist agents actual LLM tool-call access",
and issue [P6] "Enforce specialist-specific tool permissions".

This module owns four concerns:

1. Anthropic-compatible tool schemas (ToolParam dicts) for every function in
   app/tools/mock_tools.py.

2. Safe serialization of SQLAlchemy model results into plain dicts that can
   be embedded in an Anthropic tool_result message.

3. A factory (build_tool_registry) that wires a live database Session into
   each handler so specialist agents never have to import the SDK or the DB
   directly. Everything database-related stays here.

4. An authoritative specialist -> allowed-tool-names mapping
   (SPECIALIST_TOOL_PERMISSIONS) and a factory
   (build_filtered_tool_registry) that filters (3) down to only what one
   specialist is allowed to see and call. See that function's docstring
   for why this is a real security boundary and not just a convenience.

Usage by a specialist (generic, unfiltered — e.g. a one-off script):

    from app.tools.tool_registry import build_tool_registry
    from app.llm import call_llm

    tool_schemas, tool_handlers = build_tool_registry(db)
    answer = call_llm(
        system_prompt=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": message}],
        tools=(tool_schemas, tool_handlers),
    )

Usage by a specialist agent (permission-filtered — what
app/agents/specialists.py actually does):

    from app.tools.tool_registry import build_filtered_tool_registry

    tool_schemas, tool_handlers = build_filtered_tool_registry(db, "account")
    # tool_schemas/tool_handlers now contain ONLY the tools "account" is
    # allowed — see SPECIALIST_TOOL_PERMISSIONS below.
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
        "name": "check_order_issue",
        "description": (
            "Check an order for fulfillment anomalies, such as cancellation or inventory shortfalls. "
            "Call this BEFORE deciding if an order is merely delayed."
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
            schema=TOOL_SCHEMAS[4],  # check_order_issue
            handler=lambda args: mock_tools.check_order_issue(db, args["order_id"]),
        ),
        _BoundTool(
            schema=TOOL_SCHEMAS[5],  # check_payment_issue
            handler=lambda args: mock_tools.check_payment_issue(db, args["order_id"]),
        ),
        _BoundTool(
            schema=TOOL_SCHEMAS[6],  # issue_refund
            handler=lambda args: mock_tools.issue_refund(db, args["order_id"]),
        ),
        _BoundTool(
            schema=TOOL_SCHEMAS[7],  # check_room_availability
            handler=lambda args: mock_tools.check_room_availability(db, args["room_type"]),
        ),
    ]

    schemas = [b.schema for b in bound]
    handlers = {b.schema["name"]: b.handler for b in bound}
    return schemas, handlers


# ---------------------------------------------------------------------------
# Specialist tool permissions — issue [P6] "Enforce specialist-specific
# tool permissions"
# ---------------------------------------------------------------------------
#
# Why this exists: before this, every specialist called build_tool_registry()
# directly and got the FULL registry — all 8 tools, including issue_refund —
# with each specialist's system prompt in specialists.py simply instructing
# it which tools it should use. A system prompt is not an authorization
# boundary: an LLM can be jailbroken, can misread its own instructions, or a
# future prompt edit can quietly loosen what it "should" do — none of that
# should be able to turn into the Account specialist actually being able to
# issue a refund. The fix has to live in application code that runs whether
# or not the model behaves, not in wording the model is merely asked to obey.
#
# This mapping is the single authoritative source of truth for "which
# specialist may call which tool." Adjusted from a first-draft version of
# this permission list to match what each specialist's *current* system
# prompt (specialists.py) actually calls, and the tools that actually exist
# in TOOL_SCHEMAS today — not copied from an earlier draft of this feature:
#
#   - billing:   the only specialist that may ever call issue_refund, and
#                the only one that needs check_payment_issue (duplicate-
#                charge / payment-fulfillment-mismatch detection — #59).
#   - technical: read-only; grounds answers in the KB and this customer's
#                ticket history, never touches an order.
#   - order:     investigates and explains order status (including
#                check_order_issue's cancellation/inventory-shortfall
#                detection — #60) but must NEVER refund — its own system
#                prompt already says so ("Do NOT blindly issue a refund
#                here"); this mapping is what makes that a fact about the
#                system, not just an instruction the model could ignore.
#   - account:   read-only profile lookup ONLY. Its system prompt never
#                calls anything but get_customer, so that's its entire
#                allowlist — the smallest of the four, matching "Account
#                is read-only" being the whole point of that specialist.
#
# check_room_availability is deliberately in NOBODY's allowlist here: it
# belongs to the separate hotel-booking stretch feature (app/agents/
# booking.py), which uses its own dedicated registry
# (app/tools/booking_tools.py) and never touches this one at all — none of
# the four support specialists should be able to reach it either way.
SPECIALIST_TOOL_PERMISSIONS: dict[str, frozenset[str]] = {
    "billing": frozenset({
        "get_customer",
        "get_customer_orders",
        "check_payment_issue",
        "search_kb",
        "issue_refund",
    }),
    "technical": frozenset({
        "get_customer",
        "get_customer_tickets",
        "search_kb",
    }),
    "order": frozenset({
        "get_customer",
        "get_customer_orders",
        "check_order_issue",
        "search_kb",
    }),
    "account": frozenset({
        "get_customer",
    }),
}


def build_filtered_tool_registry(
    db: Session,
    specialist: str,
) -> tuple[list[dict], dict[str, Callable[..., Any]]]:
    """Return ``(tool_schemas, tool_handlers)`` containing ONLY the tools
    ``specialist`` is authorized for, per ``SPECIALIST_TOOL_PERMISSIONS``.

    This is the actual enforcement point, at two levels:

    1. Tool exposure — ``tool_schemas`` only contains schemas for allowed
       tools, so the LLM is never even shown that an unauthorized tool
       exists (it can't ask for something it was never told about).
    2. Tool execution — ``tool_handlers`` only contains callables for
       allowed tools. Even if a tool_use block somehow names an
       unauthorized tool anyway (a hallucinated name, or a name copied
       from an earlier turn/another specialist), ``call_llm``'s existing
       tool-calling loop already rejects any name not present in
       ``tool_handlers`` — see its "Unknown tool" handling in
       ``app/llm.py`` — returning a graceful, deterministic tool_result
       error instead of executing anything. That existing mechanism is
       reused deliberately rather than duplicated: a filtered handler
       dict makes "unauthorized" and "doesn't exist" indistinguishable to
       the model, which is the more secure posture (it never learns that
       a restricted tool exists at all).

    Raises ``ValueError`` for an unrecognized ``specialist`` — a
    programming-error guard (a typo'd specialist key), not a security
    check against the LLM.
    """
    if specialist not in SPECIALIST_TOOL_PERMISSIONS:
        raise ValueError(
            f"Unknown specialist {specialist!r} — must be one of "
            f"{sorted(SPECIALIST_TOOL_PERMISSIONS)}. This is a programming "
            "error (a typo'd specialist key), not something an LLM can "
            "trigger."
        )

    allowed = SPECIALIST_TOOL_PERMISSIONS[specialist]
    all_schemas, all_handlers = build_tool_registry(db)

    schemas = [s for s in all_schemas if s["name"] in allowed]
    handlers = {name: fn for name, fn in all_handlers.items() if name in allowed}
    return schemas, handlers
