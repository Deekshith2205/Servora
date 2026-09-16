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
from app.api.schemas import (
    EscalationDetailOut,
    ResolveTicketRequest,
    ResolveTicketResponse,
    TicketOut,
    CustomerProfileOut,
    CustomerHistoryTicketOut,
    AssignTicketRequest,
)
from app.auth.dependency import CurrentActor, get_current_actor, require_permission
from app.auth.investigation_visibility import can_handle_escalation, can_view_escalation_queue
from app.db.database import get_db
from app.db.models import Ticket, Customer
from app.llm import LLMError

router = APIRouter(prefix="/api", tags=["tickets"])

_FORBIDDEN_DETAIL = "You do not have permission to perform this action."


@router.get("/tickets/mine", response_model=list[TicketOut])
def list_my_tickets(
    db: Session = Depends(get_db), actor: CurrentActor = Depends(require_permission("view_own_tickets"))
) -> list[Ticket]:
    """[RBAC] issue #182 — a Customer's own real ticket status, reusing
    the existing `Ticket`/`TicketOut` machinery. Scoped strictly to the
    resolved actor's own `customer_id` — an actor with the permission
    but no real `customer_id` (should not happen, `view_own_tickets` is
    customer-only) gets a real empty list, never another customer's."""
    if actor.customer_id is None:
        return []
    return db.query(Ticket).filter(Ticket.customer_id == actor.customer_id).order_by(Ticket.created_at.desc()).all()


@router.get("/escalations", response_model=list[TicketOut])
def list_escalations(
    db: Session = Depends(get_db), actor: CurrentActor = Depends(get_current_actor)
) -> list[Ticket]:
    """[RBAC] issues #190/#196/#220: `can_view_escalation_queue()` — a
    Manager (`view_escalation_queue`) or a Support Agent/Administrator
    (`handle_escalations`) may both list the real queue; only
    `handle_escalations` holders may act on it (see the assign/resolve
    endpoints below)."""
    if not can_view_escalation_queue(actor):
        raise HTTPException(status_code=403, detail=_FORBIDDEN_DETAIL)
    return db.query(Ticket).filter(Ticket.status.in_(["open", "escalated"])).all()


@router.get("/tickets/resolved", response_model=list[TicketOut])
def list_resolved(db: Session = Depends(get_db)) -> list[Ticket]:
    return db.query(Ticket).filter(Ticket.status == "resolved").all()


@router.get("/escalations/{ticket_id}", response_model=EscalationDetailOut)
def get_escalation_detail(
    ticket_id: int, db: Session = Depends(get_db), actor: CurrentActor = Depends(get_current_actor)
) -> EscalationDetailOut:
    """[RBAC] issue #190: same `can_view_escalation_queue()` gate as the
    list endpoint — detail is a drill-down of the same queue."""
    if not can_view_escalation_queue(actor):
        raise HTTPException(status_code=403, detail=_FORBIDDEN_DETAIL)
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

    customer = db.get(Customer, ticket.customer_id)
    customer_profile = None
    if customer:
        customer_profile = CustomerProfileOut(
            id=customer.id,
            name=customer.name,
            email=customer.email,
            phone=customer.phone,
            tier=customer.tier,
        )

    previous_tickets = (
        db.query(Ticket)
        .filter(Ticket.customer_id == ticket.customer_id, Ticket.id != ticket.id)
        .order_by(Ticket.created_at.desc())
        .limit(10)
        .all()
    )
    
    customer_history = []
    for pt in previous_tickets:
        customer_history.append(
            CustomerHistoryTicketOut(
                id=pt.id,
                subject=pt.subject,
                category=pt.category,
                status=pt.status,
                sentiment=pt.sentiment,
                urgency=pt.urgency,
                created_at=pt.created_at.isoformat(),
            )
        )

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
        assigned_to=ticket.assigned_to,
        trace=json.loads(ticket.trace_json) if ticket.trace_json else None,
        handoff_packet=json.loads(ticket.handoff_packet_json) if ticket.handoff_packet_json else None,
        customer=customer_profile,
        customer_history=customer_history,
    )


@router.post("/escalations/{ticket_id}/resolve", response_model=ResolveTicketResponse)
def resolve_escalation(
    ticket_id: int,
    payload: ResolveTicketRequest,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(get_current_actor),
) -> ResolveTicketResponse:
    """[RBAC] issue #190: `can_handle_escalation()` — a real ACT
    permission, distinct from `can_view_escalation_queue()`'s read-only
    grant (a Manager can see this ticket but not resolve it)."""
    if not can_handle_escalation(actor):
        raise HTTPException(status_code=403, detail=_FORBIDDEN_DETAIL)
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


@router.post("/escalations/{ticket_id}/assign", response_model=TicketOut)
def assign_escalation(
    ticket_id: int,
    payload: AssignTicketRequest,
    db: Session = Depends(get_db),
    actor: CurrentActor = Depends(get_current_actor),
) -> TicketOut:
    """[RBAC] issue #190: `can_handle_escalation()` — the same real ACT
    permission `resolve_escalation()` requires."""
    if not can_handle_escalation(actor):
        raise HTTPException(status_code=403, detail=_FORBIDDEN_DETAIL)
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

    if ticket.status not in ["open", "escalated"]:
        raise HTTPException(status_code=400, detail="Cannot assign a closed or resolved ticket")

    if payload.assigned_to is not None:
        assigned = payload.assigned_to.strip()
        if not assigned:
            raise HTTPException(status_code=400, detail="assigned_to cannot be empty")
        if len(assigned) > 100:
            raise HTTPException(status_code=400, detail="assigned_to is too long")
        ticket.assigned_to = assigned
    else:
        ticket.assigned_to = None

    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/escalations/{ticket_id}/close", response_model=TicketOut)
def close_escalation(
    ticket_id: int, db: Session = Depends(get_db), actor: CurrentActor = Depends(get_current_actor)
) -> TicketOut:
    """[RBAC]: not explicitly named by any single issue, but the same
    real class of action `resolve`/`assign` are (an escalation-queue
    write) — gated with the same `can_handle_escalation()` check for
    consistency rather than left as an obvious, unguarded gap."""
    if not can_handle_escalation(actor):
        raise HTTPException(status_code=403, detail=_FORBIDDEN_DETAIL)
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

    if ticket.status not in ["open", "escalated"]:
        raise HTTPException(status_code=400, detail="Cannot close a ticket that is already closed or resolved")

    ticket.status = "closed"
    db.commit()
    db.refresh(ticket)
    return ticket
