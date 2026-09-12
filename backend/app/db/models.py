"""Mock data model for the demo.

Deliberately small — enough tables to make every agent (classifier, billing,
technical, order, account, booking) have something real to query instead of
hallucinating. Extend as issues need more fields, don't redesign the shape
without flagging it in #base-scaffold first since several agents will read
these directly.
"""
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
    """Backs the hotel-booking stretch feature — ignore until that issue is picked up."""

    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    room_type: Mapped[str] = mapped_column(String)
    check_in: Mapped[str] = mapped_column(String)
    check_out: Mapped[str] = mapped_column(String)
    guests: Mapped[int] = mapped_column(Integer, default=1)
    total_price: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, default="AI_DRAFTED")  # AI_DRAFTED|STAFF_REVIEWED|CONFIRMED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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
