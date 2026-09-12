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


def check_payment_issue(db: Session, order_id: int) -> dict | None:
    order = db.get(Order, order_id)
    if order is None:
        return {"detected": False, "issue_type": None, "order_id": order_id, "error": "Order not found"}
    
    if order.payment_status == "refunded" or order.status == "refunded":
        return {
            "detected": False,
            "issue_type": None,
            "order_id": order_id,
            "error": "Already refunded"
        }

    if order.duplicate_of is not None:
        return {
            "detected": True,
            "issue_type": "duplicate_payment",
            "order_id": order.id,
            "related_order_id": order.duplicate_of,
            "payment_status": order.payment_status,
            "fulfillment_status": order.status
        }
        
    if order.payment_status == "paid" and order.status == "failed":
        return {
            "detected": True,
            "issue_type": "payment_fulfillment_mismatch",
            "order_id": order.id,
            "payment_status": order.payment_status,
            "fulfillment_status": order.status
        }
        
    return {
        "detected": False,
        "issue_type": None,
        "order_id": order.id
    }


def check_order_issue(db: Session, order_id: int) -> dict:
    order = db.get(Order, order_id)
    if order is None:
        return {"detected": False, "issue_type": None, "order_id": order_id, "error": "Order not found"}
        
    if order.status == "cancelled":
        return {
            "detected": True,
            "issue_type": "cancelled_order",
            "order_id": order.id,
            "status": "cancelled"
        }
        
    if order.status == "failed" and order.failure_reason == "inventory_shortfall":
        return {
            "detected": True,
            "issue_type": "inventory_shortfall",
            "order_id": order.id,
            "status": "failed",
            "failure_reason": "inventory_shortfall"
        }
        
    return {
        "detected": False,
        "issue_type": None,
        "order_id": order.id
    }


def issue_refund(db: Session, order_id: int) -> dict:
    order = db.get(Order, order_id)
    if order is None:
        return {"success": False, "error": "Order not found"}
        
    if order.payment_status == "refunded" or order.status == "refunded":
        return {"success": False, "error": "Order already refunded"}
        
    order.payment_status = "refunded"
    order.status = "refunded"
    db.commit()
    db.refresh(order)
    return {"success": True, "order_id": order.id, "payment_status": "refunded", "status": "refunded"}


def check_room_availability(db: Session, room_type: str) -> Room | None:
    return db.query(Room).filter(Room.room_type == room_type).first()
