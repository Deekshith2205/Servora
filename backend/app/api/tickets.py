"""Escalation queue for the Staff Dashboard.

Tracked further by issue: "Staff Dashboard: escalation queue view" (frontend)
— this endpoint already returns real seeded data so that issue can start
immediately without waiting on the agent pipeline.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import TicketOut
from app.db.database import get_db
from app.db.models import Ticket

router = APIRouter(prefix="/api", tags=["tickets"])


@router.get("/escalations", response_model=list[TicketOut])
def list_escalations(db: Session = Depends(get_db)) -> list[Ticket]:
    return db.query(Ticket).filter(Ticket.status.in_(["open", "escalated"])).all()
