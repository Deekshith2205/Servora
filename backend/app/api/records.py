"""[EXPLAIN] issue #95: minimal read-only record lookups backing the
Evidence Explorer's inline preview — clicking an `order`/`customer`/
`ticket` evidence reference opens just enough real data to explain what
the evidence actually was, not a full record-management view (that's
what the Staff Dashboard is for). No new tables — these read the exact
same rows `mock_tools.py` already queries for the specialists.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from datetime import datetime, timedelta

from app.api.analytics import CHURN_HIGH_THRESHOLD, CHURN_MEDIUM_THRESHOLD
from app.api.schemas import (
    CustomerProfileOut,
    OrderRecordOut,
    PaymentRecordOut,
    ShopifyCustomerRecordOut,
    ShopifyOrderRecordOut,
    TicketRecordOut,
    CustomerHistoryTicketOut,
)
from app.auth.dependency import CurrentActor, get_current_actor
from app.auth.investigation_visibility import can_view_evidence
from app.db.database import get_db
from app.db.models import Customer, Order, Payment, Ticket

# Customer Context panel: how far back "Recent Refund Requests" looks.
_RECENT_REFUND_WINDOW_DAYS = 30
from app.services import shopify_service
from app.services.shopify_service import ShopifyAPIError, ShopifyNotConnectedError

router = APIRouter(prefix="/api/records", tags=["records"])

_FORBIDDEN_DETAIL = "You do not have permission to perform this action."

# Deliberately NOT under /api/orders, /api/customers, /api/tickets — the
# latter already has a literal route (GET /api/tickets/resolved) that a
# generic /api/tickets/{id} would collide/shadow depending on router
# registration order. A distinct /api/records/... prefix sidesteps that
# ambiguity entirely rather than depending on main.py's include_router
# ordering to keep working correctly forever.


@router.get("/orders/{order_id}", response_model=OrderRecordOut)
def get_order(
    order_id: int, db: Session = Depends(get_db), actor: CurrentActor = Depends(get_current_actor)
) -> Order:
    """[RBAC] issue #188/#218: `can_view_evidence()`, resolving the
    order's own real `customer_id` as the ownership check — staff with
    `view_evidence` can view any order; a Customer only their own."""
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    if not can_view_evidence(actor, order.customer_id):
        raise HTTPException(status_code=403, detail=_FORBIDDEN_DETAIL)
    return order


@router.get("/customers/{customer_id}", response_model=CustomerProfileOut)
def get_customer(
    customer_id: int, db: Session = Depends(get_db), actor: CurrentActor = Depends(get_current_actor)
) -> CustomerProfileOut:
    """[RBAC] issues #184 + #188/#218: this ONE endpoint serves BOTH
    the staff Evidence Explorer case (`view_evidence`) and a Customer
    viewing their OWN profile (issue #184) — `can_view_evidence()`
    covers both through the same check, using the customer record's own
    `id` as the ownership key."""
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    if not can_view_evidence(actor, customer.id):
        raise HTTPException(status_code=403, detail=_FORBIDDEN_DETAIL)

    sorted_tickets = sorted(customer.tickets, key=lambda t: t.created_at, reverse=True)
    channels_used = []
    for t in sorted_tickets:
        ch = t.channel_key or "live_chat"
        if ch not in channels_used:
            channels_used.append(ch)

    history = [
        CustomerHistoryTicketOut(
            id=t.id,
            subject=t.subject,
            category=t.category,
            status=t.status,
            sentiment=t.sentiment,
            urgency=t.urgency,
            created_at=t.created_at.isoformat(),
            channel=t.channel_key or "live_chat"
        ) for t in sorted_tickets
    ]

    payments = db.query(Payment).filter(Payment.customer_id == customer.id).order_by(Payment.charged_at.desc()).all()

    return CustomerProfileOut(
        id=customer.id,
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
        tier=customer.tier,
        previous_tickets_count=len(customer.tickets),
        risk_level=_risk_level(customer),
        channels_used=channels_used,
        conversation_history=history,
        customer_since=_customer_since(customer, payments),
        total_orders=len(customer.orders),
        last_order=_last_order(customer),
        payment_method=payments[0].method if payments and payments[0].method else None,
        recent_refund_requests=_recent_refund_requests(payments),
    )


def _customer_since(customer: Customer, payments: list[Payment]) -> str | None:
    """No `Customer.created_at` column exists (see models.py::Payment's
    docstring for why this repo avoids ALTERing an existing table) — the
    earliest real Order/Payment timestamp this customer has is a
    reasonable, honest proxy, not a fabricated date. `None` only for a
    customer with neither (shouldn't happen for a seeded/real customer,
    but not assumed)."""
    candidates = [o.created_at for o in customer.orders] + [p.charged_at for p in payments]
    return min(candidates).isoformat() if candidates else None


def _last_order(customer: Customer) -> dict | None:
    if not customer.orders:
        return None
    latest = max(customer.orders, key=lambda o: o.created_at)
    return {"product": latest.product, "status": latest.status, "created_at": latest.created_at.isoformat()}


def _recent_refund_requests(payments: list[Payment]) -> list[dict]:
    cutoff = datetime.utcnow() - timedelta(days=_RECENT_REFUND_WINDOW_DAYS)
    recent = [
        p for p in payments
        if p.status in ("refund_pending", "refunded")
        and (p.refund_requested_at or p.refunded_at or p.charged_at) >= cutoff
    ]
    return [
        {
            "payment_id": p.id,
            "amount": p.amount,
            "status": p.status,
            "requested_at": (p.refund_requested_at or p.charged_at).isoformat(),
        }
        for p in recent
    ]


def _risk_level(customer: Customer) -> str | None:
    """[Explainability #123]: reuses analytics.py's existing churn-risk
    thresholds (a customer with several unresolved tickets is worth
    flagging) rather than inventing a second set of numbers — applied
    here to one customer's own ALL-TIME ticket history (a single-record
    detail view has no natural "lookback window" the way the Analytics
    tab's time-boxed churn signal does). `None` (not "low") when there's
    nothing concerning to report — a customer with zero or one
    unresolved ticket isn't meaningfully "low risk", they're simply
    unflagged, the same distinction compute_churn_signals() already
    draws by omitting them entirely rather than fabricating a floor
    value."""
    unresolved = sum(1 for t in customer.tickets if t.status in ("open", "escalated"))
    if unresolved < CHURN_MEDIUM_THRESHOLD:
        return None
    return "high" if unresolved >= CHURN_HIGH_THRESHOLD else "medium"


@router.get("/payments/{payment_id}", response_model=PaymentRecordOut)
def get_payment(
    payment_id: int, db: Session = Depends(get_db), actor: CurrentActor = Depends(get_current_actor)
) -> PaymentRecordOut:
    """Mirrors get_order() exactly — backs a "payment" evidence
    reference's inline preview in the Explainability drawer."""
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")
    if not can_view_evidence(actor, payment.customer_id):
        raise HTTPException(status_code=403, detail=_FORBIDDEN_DETAIL)
    return PaymentRecordOut(
        id=payment.id,
        customer_id=payment.customer_id,
        order_id=payment.order_id,
        amount=payment.amount,
        method=payment.method,
        description=payment.description,
        status=payment.status,
        payment_type=payment.payment_type,
        duplicate_of=payment.duplicate_of,
        charged_at=payment.charged_at.isoformat(),
    )


@router.get("/tickets/{ticket_id}", response_model=TicketRecordOut)
def get_ticket(
    ticket_id: int, db: Session = Depends(get_db), actor: CurrentActor = Depends(get_current_actor)
) -> TicketRecordOut:
    """[RBAC] issue #188/#218: same `can_view_evidence()` check,
    resolving the ticket's own `customer_id`."""
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    if not can_view_evidence(actor, ticket.customer_id):
        raise HTTPException(status_code=403, detail=_FORBIDDEN_DETAIL)
    return TicketRecordOut(
        id=ticket.id,
        customer_id=ticket.customer_id,
        category=ticket.category,
        subject=ticket.subject,
        status=ticket.status,
        sentiment=ticket.sentiment,
        urgency=ticket.urgency,
        created_at=ticket.created_at.isoformat(),
    )


# --------------------------------------------------------------------- #
# Shopify integration: backs a `shopify_order`/`shopify_customer`
# evidence reference's inline preview — same role as the lookups above,
# just re-querying a live Shopify store instead of Servora's own DB (see
# app/services/shopify_service.py). Deliberately re-fetches live rather
# than caching the tool call's original result: by the time a user opens
# this preview, the order may have genuinely changed (e.g. fulfillment
# status), and this endpoint's whole point is showing the CURRENT real
# record, not a stale snapshot.
# --------------------------------------------------------------------- #


@router.get("/shopify-orders/{order_id}", response_model=ShopifyOrderRecordOut)
def get_shopify_order(order_id: int, db: Session = Depends(get_db)) -> ShopifyOrderRecordOut:
    try:
        order = shopify_service.get_order(db, order_id)
    except ShopifyNotConnectedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ShopifyAPIError as exc:
        raise HTTPException(status_code=502, detail=f"Shopify lookup failed: {exc}") from exc
    if order is None:
        raise HTTPException(status_code=404, detail=f"Shopify order {order_id} not found")
    return ShopifyOrderRecordOut(
        id=order["id"],
        order_number=order.get("name"),
        email=order.get("email"),
        total_price=order.get("total_price"),
        financial_status=order.get("financial_status"),
        fulfillment_status=order.get("fulfillment_status"),
        created_at=order.get("created_at"),
    )


@router.get("/shopify-customers/{customer_id}", response_model=ShopifyCustomerRecordOut)
def get_shopify_customer(customer_id: int, db: Session = Depends(get_db)) -> ShopifyCustomerRecordOut:
    try:
        customer = shopify_service.get_customer(db, customer_id)
    except ShopifyNotConnectedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ShopifyAPIError as exc:
        raise HTTPException(status_code=502, detail=f"Shopify lookup failed: {exc}") from exc
    if customer is None:
        raise HTTPException(status_code=404, detail=f"Shopify customer {customer_id} not found")
    return ShopifyCustomerRecordOut(
        id=customer["id"],
        first_name=customer.get("first_name"),
        last_name=customer.get("last_name"),
        email=customer.get("email"),
        orders_count=customer.get("orders_count"),
        total_spent=customer.get("total_spent"),
    )
