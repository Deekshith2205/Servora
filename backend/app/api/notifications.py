"""Read-only listing of customer notifications. Issue #21 — see
app/services/notifications.py for what actually creates these rows and why
this is a recorded row rather than a real email/SMS send.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import NotificationOut
from app.auth.dependency import CurrentActor, get_current_actor
from app.auth.roles import CUSTOMER
from app.db.database import get_db
from app.db.models import Notification

router = APIRouter(prefix="/api", tags=["notifications"])


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    db: Session = Depends(get_db), actor: CurrentActor = Depends(get_current_actor)
) -> list[Notification]:
    """[RBAC] issue #185: actor-scoping, not a new permission gate — a
    Customer sees only their own `customer_id`'s rows; every staff
    caller (today's only real caller, the Staff Dashboard's booking
    drawer) is completely unaffected, matching the issue's own explicit
    "otherwise unchanged for staff callers" requirement."""
    query = db.query(Notification)
    if actor.role == CUSTOMER:
        query = query.filter(Notification.customer_id == actor.customer_id)
    return query.order_by(Notification.created_at.desc()).all()
