"""Escalation queue for the Staff Dashboard.

The list endpoint returns real seeded data (and, since issue #14, real
tickets created by /api/chat escalations too — see
orchestrator.py::_create_escalation_ticket()). The detail endpoint
(issue #14) is what lets a staff member click into one ticket and see
exactly what the AI tried, not just the summary row.
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import EscalationDetailOut, TicketOut
from app.db.database import get_db
from app.db.models import Ticket

router = APIRouter(prefix="/api", tags=["tickets"])


@router.get("/escalations", response_model=list[TicketOut])
def list_escalations(db: Session = Depends(get_db)) -> list[Ticket]:
    return db.query(Ticket).filter(Ticket.status.in_(["open", "escalated"])).all()


@router.get("/escalations/{ticket_id}", response_model=EscalationDetailOut)
def get_escalation_detail(ticket_id: int, db: Session = Depends(get_db)) -> EscalationDetailOut:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

    return EscalationDetailOut(
        id=ticket.id,
        customer_id=ticket.customer_id,
        category=ticket.category,
        subject=ticket.subject,
        message=ticket.message,
        sentiment=ticket.sentiment,
        urgency=ticket.urgency,
        status=ticket.status,
        trace=json.loads(ticket.trace_json) if ticket.trace_json else None,
        handoff_packet=json.loads(ticket.handoff_packet_json) if ticket.handoff_packet_json else None,
    )
