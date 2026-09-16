from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.api.schemas import InboxItemOut, InboxDetailOut, CompactCustomerOut
from app.db.database import get_db
from app.db.models import Ticket, Investigation, Channel

router = APIRouter(prefix="/api/inbox", tags=["inbox"])

@router.get("", response_model=list[InboxItemOut])
def list_inbox(channel: str | None = None, db: Session = Depends(get_db)) -> list[InboxItemOut]:
    """
    Unified Inbox Phase 2: One row per Ticket, forming the conversational list view.
    Does not duplicate records if an investigation exists.
    """
    if channel:
        valid_channel = db.query(Channel).filter(Channel.key == channel).first()
        if not valid_channel:
            raise HTTPException(status_code=400, detail=f"Invalid channel '{channel}'.")

    query = (
        db.query(Ticket, Investigation.id.label("investigation_id"))
        .outerjoin(Investigation, Investigation.ticket_id == Ticket.id)
        .options(joinedload(Ticket.customer))
    )

    if channel:
        query = query.filter(Ticket.channel_key == channel)

    results = query.order_by(Ticket.created_at.desc()).all()
    
    inbox_items = []
    for ticket, inv_id in results:
        preview = ticket.message[:100] + ("..." if len(ticket.message) > 100 else "")
        inbox_items.append(
            InboxItemOut(
                id=ticket.id,
                customer=CompactCustomerOut(
                    id=ticket.customer.id,
                    name=ticket.customer.name,
                    email=ticket.customer.email
                ),
                channel_key=ticket.channel_key,
                subject=ticket.subject,
                preview=preview,
                status=ticket.status,
                updated_at=ticket.created_at.isoformat(),
                has_investigation=inv_id is not None
            )
        )
    return inbox_items


@router.get("/{ticket_id}", response_model=InboxDetailOut)
def get_inbox_detail(ticket_id: int, db: Session = Depends(get_db)) -> InboxDetailOut:
    """
    Unified Inbox Phase 2: Details for the selected conversation panel.
    Returns real ticket/customer data without the massive overhead of the full Investigation.
    """
    result = (
        db.query(Ticket, Investigation.id.label("investigation_id"))
        .outerjoin(Investigation, Investigation.ticket_id == Ticket.id)
        .options(joinedload(Ticket.customer))
        .filter(Ticket.id == ticket_id)
        .first()
    )
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Conversation {ticket_id} not found")
        
    ticket, inv_id = result
    
    return InboxDetailOut(
        id=ticket.id,
        customer=CompactCustomerOut(
            id=ticket.customer.id,
            name=ticket.customer.name,
            email=ticket.customer.email
        ),
        channel_key=ticket.channel_key,
        subject=ticket.subject,
        message=ticket.message,
        status=ticket.status,
        updated_at=ticket.created_at.isoformat(),
        investigation_id=inv_id
    )
