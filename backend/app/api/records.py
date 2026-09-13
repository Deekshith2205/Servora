"""[EXPLAIN] issue #95: minimal read-only record lookups backing the
Evidence Explorer's inline preview — clicking an `order`/`customer`/
`ticket` evidence reference opens just enough real data to explain what
the evidence actually was, not a full record-management view (that's
what the Staff Dashboard is for). No new tables — these read the exact
same rows `mock_tools.py` already queries for the specialists.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import CustomerProfileOut, OrderRecordOut, TicketRecordOut
from app.db.database import get_db
from app.db.models import Customer, Order, Ticket

router = APIRouter(prefix="/api/records", tags=["records"])

# Deliberately NOT under /api/orders, /api/customers, /api/tickets — the
# latter already has a literal route (GET /api/tickets/resolved) that a
# generic /api/tickets/{id} would collide/shadow depending on router
# registration order. A distinct /api/records/... prefix sidesteps that
# ambiguity entirely rather than depending on main.py's include_router
# ordering to keep working correctly forever.


@router.get("/orders/{order_id}", response_model=OrderRecordOut)
def get_order(order_id: int, db: Session = Depends(get_db)) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return order


@router.get("/customers/{customer_id}", response_model=CustomerProfileOut)
def get_customer(customer_id: int, db: Session = Depends(get_db)) -> Customer:
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return customer


@router.get("/tickets/{ticket_id}", response_model=TicketRecordOut)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)) -> TicketRecordOut:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
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
