"""[EXPLAIN] issue #95: minimal read-only record lookups backing the
Evidence Explorer's inline preview — clicking an `order`/`customer`/
`ticket` evidence reference opens just enough real data to explain what
the evidence actually was, not a full record-management view (that's
what the Staff Dashboard is for). No new tables — these read the exact
same rows `mock_tools.py` already queries for the specialists.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.analytics import CHURN_HIGH_THRESHOLD, CHURN_MEDIUM_THRESHOLD
from app.api.schemas import (
    CustomerProfileOut,
    OrderRecordOut,
    ShopifyCustomerRecordOut,
    ShopifyOrderRecordOut,
    TicketRecordOut,
)
from app.auth.dependency import CurrentActor, get_current_actor
from app.auth.investigation_visibility import can_view_evidence
from app.db.database import get_db
from app.db.models import Customer, Order, Ticket
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
    return CustomerProfileOut(
        id=customer.id,
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
        tier=customer.tier,
        previous_tickets_count=len(customer.tickets),
        risk_level=_risk_level(customer),
    )


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
