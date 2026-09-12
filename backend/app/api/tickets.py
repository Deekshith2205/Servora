"""Escalation queue for the Staff Dashboard.

The list endpoint returns real seeded data (and, since issue #14, real
tickets created by /api/chat escalations too — see
orchestrator.py::_create_escalation_ticket()). The detail endpoint
(issue #14) is what lets a staff member click into one ticket and see
exactly what the AI tried, not just the summary row. The resolve
endpoint (issue #17) is what triggers the Learning Agent — see
app/agents/learning.py and app/api/kb.py for the approval step.
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.learning import draft_kb_article
from app.api.schemas import EscalationDetailOut, ResolveTicketRequest, ResolveTicketResponse, TicketOut
from app.db.database import get_db
from app.db.models import Ticket
from app.llm import LLMError

router = APIRouter(prefix="/api", tags=["tickets"])


@router.get("/escalations", response_model=list[TicketOut])
def list_escalations(db: Session = Depends(get_db)) -> list[Ticket]:
    return db.query(Ticket).filter(Ticket.status.in_(["open", "escalated"])).all()


@router.get("/tickets/resolved", response_model=list[TicketOut])
def list_resolved(db: Session = Depends(get_db)) -> list[Ticket]:
    return db.query(Ticket).filter(Ticket.status == "resolved").all()


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
        confidence=ticket.confidence,
        trace=json.loads(ticket.trace_json) if ticket.trace_json else None,
        handoff_packet=json.loads(ticket.handoff_packet_json) if ticket.handoff_packet_json else None,
    )


@router.post("/escalations/{ticket_id}/resolve", response_model=ResolveTicketResponse)
def resolve_escalation(
    ticket_id: int, payload: ResolveTicketRequest, db: Session = Depends(get_db)
) -> ResolveTicketResponse:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

    ticket.status = "resolved"
    db.commit()
    db.refresh(ticket)

    handoff_packet = json.loads(ticket.handoff_packet_json) if ticket.handoff_packet_json else {}

    # Best-effort, same pattern as orchestrator.py's _update_memory(): a
    # failed draft must never block marking the ticket resolved.
    kb_suggestion = None
    try:
        draft = draft_kb_article(
            category=ticket.category,
            customer_message=ticket.message,
            resolution_notes=payload.resolution_notes,
            root_cause_hypothesis=handoff_packet.get("root_cause_hypothesis"),
            recommended_action=handoff_packet.get("recommended_action"),
        )
        kb_suggestion = {
            "should_add": draft.should_add,
            "title": draft.title,
            "body": draft.body,
            "tags": draft.tags,
        }
    except LLMError:
        pass  # ticket is still resolved; just no KB suggestion this time

    return ResolveTicketResponse(ticket=ticket, kb_suggestion=kb_suggestion)
