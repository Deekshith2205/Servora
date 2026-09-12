"""Mock data model for the demo.

Deliberately small — enough tables to make every agent (classifier, billing,
technical, order, account, booking) have something real to query instead of
hallucinating. Extend as issues need more fields, don't redesign the shape
without flagging it in #base-scaffold first since several agents will read
these directly.
"""
import json
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True)
    phone: Mapped[str] = mapped_column(String, default="")
    tier: Mapped[str] = mapped_column(String, default="standard")  # standard | vip

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    product: Mapped[str] = mapped_column(String)
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="processing")  # processing|shipped|delivered|refunded
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer: Mapped["Customer"] = relationship(back_populates="orders")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    category: Mapped[str] = mapped_column(String, default="")  # billing|technical|order|account
    subject: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(String)
    sentiment: Mapped[str] = mapped_column(String, default="")  # positive|neutral|negative
    urgency: Mapped[int] = mapped_column(Integer, default=0)  # 1-10
    status: Mapped[str] = mapped_column(String, default="open")  # open|resolved|escalated
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Issue #14: JSON-encoded snapshots of the reasoning trace and handoff
    # packet from the /api/chat call that created this ticket (only set on
    # tickets created by a real escalation — nullable so the seeded demo
    # tickets, which never went through the pipeline, are unaffected).
    trace_json: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    handoff_packet_json: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    customer: Mapped["Customer"] = relationship(back_populates="tickets")


class KBArticle(Base):
    __tablename__ = "kb_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)
    tags: Mapped[str] = mapped_column(String, default="")  # comma-separated


class Room(Base):
    """Backs the hotel-booking stretch feature — ignore until that issue is picked up."""

    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_type: Mapped[str] = mapped_column(String)  # standard|deluxe|suite
    price_per_night: Mapped[float] = mapped_column(Float)
    total_count: Mapped[int] = mapped_column(Integer)


class Booking(Base):
    """Backs the hotel-booking stretch feature. Issue #18 (Booking Agent)
    creates rows here at status="AI_DRAFTED"; issue #20 (staff review/edit)
    is what actually reads/writes `edit_log_json` and drives the rest of
    the state machine (see docs/ARCHITECTURE.md): every edit made once a
    booking exists is logged (old value -> new value), and issue #21
    consumes that log to tell the customer exactly what changed.
    """

    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    room_type: Mapped[str] = mapped_column(String)
    check_in: Mapped[str] = mapped_column(String)
    check_out: Mapped[str] = mapped_column(String)
    guests: Mapped[int] = mapped_column(Integer, default=1)
    total_price: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, default="AI_DRAFTED")  # AI_DRAFTED|STAFF_REVIEWED|CONFIRMED
    # Issue #20: JSON-encoded list of {field, old_value, new_value, at} —
    # every staff edit appended, oldest first. A flat log (not a richer
    # schema) since the only consumer (#21's notification diff) just needs
    # to render "field changed from X to Y".
    edit_log_json: Mapped[str] = mapped_column(String, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @property
    def edit_log(self) -> list[dict]:
        """Parsed view of `edit_log_json` — lets BookingDetailOut's Pydantic
        `from_attributes` mode read it like any other attribute instead of
        every caller having to `json.loads` it themselves."""
        return json.loads(self.edit_log_json) if self.edit_log_json else []


class CustomerMemory(Base):
    """Backs issue #11 (customer memory write/merge) — see app/agents/memory.py.

    One row per customer. `facts_json` is a JSON-encoded list of short,
    durable fact strings (preferences, exceptions granted, recurring
    patterns) — deliberately a flat list, not a rich schema, since the only
    operation that matters is a set-union merge.
    """

    __tablename__ = "customer_memory"

    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), primary_key=True)
    facts_json: Mapped[str] = mapped_column(String, default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Notification(Base):
    """Backs issue #21 (customer notification on booking edit).

    Deliberately NOT a real email/SMS send — see
    app/services/notifications.py's module docstring for why. This table
    is the durable, queryable record of "a notification was sent" (visible
    in the Staff Dashboard's booking drawer, and easy to assert against in
    tests) that a real provider integration would sit behind later without
    changing anything that calls `notify_customer_of_booking_edit`.
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    subject: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
