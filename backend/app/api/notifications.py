"""Read-only listing of customer notifications. Issue #21 — see
app/services/notifications.py for what actually creates these rows and why
this is a recorded row rather than a real email/SMS send.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import NotificationOut
from app.db.database import get_db
from app.db.models import Notification

router = APIRouter(prefix="/api", tags=["notifications"])


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(db: Session = Depends(get_db)) -> list[Notification]:
    return db.query(Notification).order_by(Notification.created_at.desc()).all()
