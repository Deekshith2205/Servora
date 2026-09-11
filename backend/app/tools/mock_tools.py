"""Tool functions every specialist agent calls instead of answering from
model memory. Keep this rule when extending: an agent must call a tool to
state any fact about a customer, order, ticket, or policy — never assert it
from the prompt alone. That's what keeps the demo from hallucinating an
order number live in front of judges.

These are intentionally plain functions (not yet wired to an LLM tool-call
schema) — issue #4 (Planner/Orchestrator routing) and the specialist-agent
issues wrap these with real tool-calling.
"""
from sqlalchemy.orm import Session

from app.db.models import Customer, KBArticle, Order, Room, Ticket


def get_customer(db: Session, customer_id: int) -> Customer | None:
    return db.get(Customer, customer_id)


def get_customer_orders(db: Session, customer_id: int) -> list[Order]:
    return db.query(Order).filter(Order.customer_id == customer_id).all()


def get_customer_tickets(db: Session, customer_id: int) -> list[Ticket]:
    return db.query(Ticket).filter(Ticket.customer_id == customer_id).all()


def search_kb(db: Session, query: str) -> list[KBArticle]:
    """Naive keyword match for the MVP — swap for embeddings in a later issue."""
    q = query.lower()
    return [a for a in db.query(KBArticle).all() if q in a.title.lower() or q in a.body.lower() or q in a.tags.lower()]


def issue_refund(db: Session, order_id: int) -> Order | None:
    order = db.get(Order, order_id)
    if order is None:
        return None
    order.status = "refunded"
    db.commit()
    db.refresh(order)
    return order


def check_room_availability(db: Session, room_type: str) -> Room | None:
    return db.query(Room).filter(Room.room_type == room_type).first()
