"""Tool functions + Anthropic tool-calling registry for the Booking Agent.
Implements issue #18 "[P4] Booking Agent: slot-filling + room availability +
AI_DRAFTED state".

Kept separate from app/tools/tool_registry.py (used by the support-ticket
specialists) rather than added to that shared registry: the booking tools
are irrelevant to billing/technical/order/account, and mixing them in would
just give every specialist's tool-calling loop two extra, confusing options
it should never call.

Design note on error handling: a business-logic problem (bad dates, no
availability) is returned as a normal dict result (`{"available": False,
"reason": "..."}`), NOT raised as an exception. call_llm's tool-execution
loop catches any exception a handler raises and replaces it with a generic
"Tool execution failed" message (deliberately, so DB details/tracebacks
never reach the model) — that would swallow the specific reason the
Booking Agent needs to read back to the customer (e.g. "no suite rooms left
for those dates, want to try different dates?"). Only a truly unexpected
failure should raise here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.db.models import Booking, Room

VALID_ROOM_TYPES = ("standard", "deluxe", "suite")


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def check_availability(
    db: Session, room_type: str, check_in: str, check_out: str, guests: int
) -> dict:
    """Return an availability + price quote, or `{"available": False, "reason": ...}`.

    Availability = room.total_count minus the count of existing, non-cancelled
    bookings of the same room_type whose date range overlaps the requested
    one. Dates are stored/compared as ISO "YYYY-MM-DD" strings, which sort
    lexicographically identically to date order — the same convention the
    `Booking` model already uses for its `check_in`/`check_out` columns.
    """
    if room_type not in VALID_ROOM_TYPES:
        return {
            "available": False,
            "reason": f"Unknown room type {room_type!r}. Valid types: "
            + ", ".join(VALID_ROOM_TYPES) + ".",
        }

    d_in, d_out = _parse_date(check_in), _parse_date(check_out)
    if d_in is None or d_out is None:
        return {"available": False, "reason": "Dates must be in YYYY-MM-DD format."}
    if d_out <= d_in:
        return {"available": False, "reason": "Check-out date must be after check-in date."}
    if guests is not None and guests < 1:
        return {"available": False, "reason": "Guest count must be at least 1."}

    room = db.query(Room).filter(Room.room_type == room_type).first()
    if room is None:
        return {"available": False, "reason": f"No {room_type} rooms are configured."}

    overlapping = (
        db.query(Booking)
        .filter(
            Booking.room_type == room_type,
            Booking.status != "cancelled",
            Booking.check_in < check_out,
            Booking.check_out > check_in,
        )
        .count()
    )
    available_rooms = room.total_count - overlapping
    if available_rooms <= 0:
        return {
            "available": False,
            "reason": f"No {room_type} rooms are available for those dates.",
        }

    nights = (d_out - d_in).days
    total_price = round(nights * room.price_per_night, 2)
    return {
        "available": True,
        "room_type": room_type,
        "check_in": check_in,
        "check_out": check_out,
        "guests": guests,
        "nights": nights,
        "price_per_night": room.price_per_night,
        "total_price": total_price,
        "available_rooms": available_rooms,
    }


def create_draft_booking(
    db: Session, customer_id: int, room_type: str, check_in: str, check_out: str, guests: int
) -> dict:
    """Re-validates availability (never trust the model's earlier claim) and,
    only if it still holds, creates the `Booking` row with status
    "AI_DRAFTED". Returns `{"created": False, "reason": ...}` on failure so
    the model can read back why and adjust, same as `check_availability`.
    """
    availability = check_availability(db, room_type, check_in, check_out, guests)
    if not availability.get("available"):
        return {"created": False, "reason": availability.get("reason", "Not available.")}

    booking = Booking(
        customer_id=customer_id,
        room_type=room_type,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        total_price=availability["total_price"],
        status="AI_DRAFTED",
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return {"created": True, "booking": booking}


# ---------------------------------------------------------------------------
# Anthropic tool schemas + registry factory (mirrors app/tools/tool_registry.py)
# ---------------------------------------------------------------------------

BOOKING_TOOL_SCHEMAS: list[dict] = [
    {
        "name": "check_availability",
        "description": (
            "Check whether a room is available for a given date range and get "
            "the exact nightly rate and total price. ALWAYS call this before "
            "quoting a price or telling the customer a room is available — "
            "never state a price from memory."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "room_type": {
                    "type": "string",
                    "description": "Room category: standard, deluxe, or suite.",
                },
                "check_in": {
                    "type": "string",
                    "description": "Check-in date, YYYY-MM-DD.",
                },
                "check_out": {
                    "type": "string",
                    "description": "Check-out date, YYYY-MM-DD.",
                },
                "guests": {
                    "type": "integer",
                    "description": "Number of guests staying.",
                },
            },
            "required": ["room_type", "check_in", "check_out", "guests"],
        },
    },
    {
        "name": "create_draft_booking",
        "description": (
            "Create the booking once the customer has explicitly confirmed the "
            "room, dates, and total price from check_availability. Creates the "
            "booking with status AI_DRAFTED — it still needs hotel staff review "
            "before it's fully confirmed. Call this AT MOST ONCE per "
            "conversation, and only after an explicit customer confirmation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "room_type": {
                    "type": "string",
                    "description": "Room category: standard, deluxe, or suite.",
                },
                "check_in": {
                    "type": "string",
                    "description": "Check-in date, YYYY-MM-DD.",
                },
                "check_out": {
                    "type": "string",
                    "description": "Check-out date, YYYY-MM-DD.",
                },
                "guests": {
                    "type": "integer",
                    "description": "Number of guests staying.",
                },
            },
            "required": ["room_type", "check_in", "check_out", "guests"],
        },
    },
]


def _serialize_booking(booking: Booking) -> dict:
    return {
        "id": booking.id,
        "customer_id": booking.customer_id,
        "room_type": booking.room_type,
        "check_in": booking.check_in,
        "check_out": booking.check_out,
        "guests": booking.guests,
        "total_price": booking.total_price,
        "status": booking.status,
    }


@dataclass
class _BoundBookingTool:
    schema: dict
    handler: Callable[[dict], Any]


def build_booking_tool_registry(
    db: Session, customer_id: int
) -> tuple[list[dict], dict[str, Callable[[dict], Any]], list[Booking]]:
    """Return `(tool_schemas, tool_handlers, created_bookings)`.

    `created_bookings` is a list this function's own `create_draft_booking`
    handler appends to as a side effect — the same "mutable list captured by
    closure" pattern `call_llm`'s `tool_call_log` already uses — so the
    caller can find out whether (and which) booking got created during the
    tool-calling loop without re-querying the DB by timestamp.
    """
    created_bookings: list[Booking] = []

    def _handle_check_availability(args: dict) -> dict:
        return check_availability(
            db, args["room_type"], args["check_in"], args["check_out"], args["guests"]
        )

    def _handle_create_draft_booking(args: dict) -> dict:
        result = create_draft_booking(
            db, customer_id, args["room_type"], args["check_in"], args["check_out"], args["guests"]
        )
        if result.get("created"):
            created_bookings.append(result["booking"])
            return {"created": True, "booking": _serialize_booking(result["booking"])}
        return result

    bound = [
        _BoundBookingTool(BOOKING_TOOL_SCHEMAS[0], _handle_check_availability),
        _BoundBookingTool(BOOKING_TOOL_SCHEMAS[1], _handle_create_draft_booking),
    ]
    schemas = [b.schema for b in bound]
    handlers = {b.schema["name"]: b.handler for b in bound}
    return schemas, handlers, created_bookings
