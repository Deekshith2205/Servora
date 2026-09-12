"""Booking Agent. Implements issue #18 "[P4] Booking Agent: slot-filling +
room availability + AI_DRAFTED state" — a hotel-booking stretch feature, see
docs/ARCHITECTURE.md and CLAUDE.md's "Key decisions" for the state machine
(`AI_DRAFTED -> STAFF_REVIEWED -> CONFIRMED`; issue #20 owns the staff side
of that transition, this agent only ever produces `AI_DRAFTED`).

State model: unlike the support-ticket specialists (each `resolve_x()` call
is a single, independent message — see app/agents/specialists.py), a
booking is inherently a multi-turn slot-filling conversation (room type,
dates, guests, one question at a time). Rather than invent new
server-side "in-progress booking" persistence, this agent is stateless
per call: the caller (POST /api/booking) passes the FULL conversation
transcript each turn, in the same {role, content} shape `call_llm` already
accepts — the frontend accumulates it exactly like it already does for
plain display purposes in CustomerChat. Once a booking is actually
created, the system prompt tells the agent to stop — any further changes
go through the staff review flow (#20), not back through this chat.
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db.models import Booking
from app.llm import call_llm
from app.tools.booking_tools import build_booking_tool_registry


@dataclass
class BookingAgentResult:
    reply: str
    booking: Booking | None = None
    used_tools: list[str] = field(default_factory=list)


_SYSTEM_PROMPT = """You are the Booking Agent for a hotel, having a live \
conversation with a customer who wants to book a room. Room types are \
standard, deluxe, and suite — but always confirm the live price via \
check_availability rather than quoting one from memory.

Slot-fill the following, asking ONE question at a time for whatever is \
still missing (don't ask for everything at once):
  - room_type (standard / deluxe / suite)
  - check_in date (YYYY-MM-DD)
  - check_out date (YYYY-MM-DD)
  - number of guests

Once you have all four, call check_availability to confirm the room is \
actually available and get the exact total price — never state a price \
you haven't gotten from the tool. Tell the customer the total price and \
ask them to explicitly confirm before booking anything.

Only after the customer has explicitly confirmed, call create_draft_booking \
to create the booking. Call it AT MOST ONCE per conversation. After it \
succeeds, tell the customer the booking is drafted and still needs a final \
review from hotel staff before it's fully confirmed — never say the \
booking is "confirmed", since it isn't yet.

If the customer wants to change something after a booking has already been \
created in this conversation, tell them a staff member will need to make \
that change — you cannot edit an existing booking here.

If check_availability or create_draft_booking reports the room isn't \
available, say so plainly and ask if they'd like different dates or a \
different room type — never claim availability the tool didn't confirm.
"""


def run_booking_agent(
    db: Session, customer_id: int, messages: list[dict], max_tokens: int = 1000
) -> BookingAgentResult:
    tool_schemas, tool_handlers, created_bookings = build_booking_tool_registry(db, customer_id)
    used_tools: list[str] = []

    reply = call_llm(
        system_prompt=_SYSTEM_PROMPT,
        messages=messages,
        tools=(tool_schemas, tool_handlers),
        tool_call_log=used_tools,
        max_tokens=max_tokens,
    )

    return BookingAgentResult(
        reply=reply,
        booking=created_bookings[-1] if created_bookings else None,
        used_tools=used_tools,
    )
