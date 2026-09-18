"""Tool functions every specialist agent calls instead of answering from
model memory. Keep this rule when extending: an agent must call a tool to
state any fact about a customer, order, ticket, or policy — never assert it
from the prompt alone. That's what keeps the demo from hallucinating an
order number live in front of judges.

These are intentionally plain functions (not yet wired to an LLM tool-call
schema) — issue #4 (Planner/Orchestrator routing) and the specialist-agent
issues wrap these with real tool-calling.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import Customer, KBArticle, Order, Payment, Room, Ticket

# Matches the seeded "Refund policy" KB article's own "5-7 business days"
# wording — a refund still pending past this many days is a real anomaly,
# not just normal processing time.
REFUND_DELAY_THRESHOLD_DAYS = 7


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

    # [Future Scope] issue #301 — a real, dated SLA check: only orders
    # with an actual promised_delivery_date on file can be judged
    # "delayed," and only if it has genuinely passed and the order still
    # isn't delivered. Replaces the old "processing/shipped for an
    # unusually long time" guesswork with a real comparison wherever a
    # promised date exists; orders with none simply skip this check
    # (honestly not evaluable), same as before this field existed.
    if (
        order.status in ("processing", "shipped")
        and order.promised_delivery_date is not None
        and order.promised_delivery_date < datetime.utcnow()
    ):
        return {
            "detected": True,
            "issue_type": "delayed_past_promised_date",
            "order_id": order.id,
            "status": order.status,
            "promised_delivery_date": order.promised_delivery_date.isoformat(),
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


def get_customer_payments(db: Session, customer_id: int) -> list[Payment]:
    return db.query(Payment).filter(Payment.customer_id == customer_id).all()


def check_payment_anomaly(db: Session, payment_id: int) -> dict:
    """Covers the 3 payment-only anomaly types that `check_payment_issue`
    (which always assumes a linked `Order`) can't represent: a duplicate
    charge with no order ever created, a subscription charged after
    cancellation, and a refund stuck pending past the policy window.
    Same dict shape as `check_payment_issue` for consistency."""
    payment = db.get(Payment, payment_id)
    if payment is None:
        return {"detected": False, "issue_type": None, "payment_id": payment_id, "error": "Payment not found"}

    if payment.status == "refunded":
        return {"detected": False, "issue_type": None, "payment_id": payment_id, "error": "Already refunded"}

    if payment.duplicate_of is not None and payment.order_id is None:
        return {
            "detected": True,
            "issue_type": "duplicate_payment_no_order",
            "payment_id": payment.id,
            "related_payment_id": payment.duplicate_of,
            "status": payment.status,
        }

    if payment.payment_type == "subscription" and payment.subscription_cancelled_at is not None:
        if payment.charged_at > payment.subscription_cancelled_at:
            return {
                "detected": True,
                "issue_type": "subscription_charged_after_cancellation",
                "payment_id": payment.id,
                "charged_at": payment.charged_at.isoformat(),
                "subscription_cancelled_at": payment.subscription_cancelled_at.isoformat(),
            }

    if payment.status == "refund_pending" and payment.refund_requested_at is not None:
        days_pending = (datetime.utcnow() - payment.refund_requested_at).days
        if days_pending >= REFUND_DELAY_THRESHOLD_DAYS:
            return {
                "detected": True,
                "issue_type": "refund_delayed",
                "payment_id": payment.id,
                "days_pending": days_pending,
            }

    return {"detected": False, "issue_type": None, "payment_id": payment.id}


def issue_payment_refund(db: Session, payment_id: int) -> dict:
    payment = db.get(Payment, payment_id)
    if payment is None:
        return {"success": False, "error": "Payment not found"}

    if payment.status == "refunded":
        return {"success": False, "error": "Payment already refunded"}

    payment.status = "refunded"
    payment.refunded_at = datetime.utcnow()
    db.commit()
    db.refresh(payment)
    return {"success": True, "payment_id": payment.id, "status": "refunded"}
