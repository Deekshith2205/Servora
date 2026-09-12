"""Staff booking review/edit endpoints. Implements issue #20 "[P4] Staff
booking review/edit UI (STAFF_REVIEWED -> CONFIRMED)" — see docs/
ARCHITECTURE.md's state machine and app/db/models.py::Booking.edit_log_json.

State transitions this module owns:
  - Any edit to a still-mutable booking logs the change and, the first
    time, bumps AI_DRAFTED -> STAFF_REVIEWED (a booking a staff member
    has touched, whether or not they changed anything the second time).
  - `POST /{id}/confirm` moves it the rest of the way to CONFIRMED.
  - Once CONFIRMED, a booking is immutable here — further changes are out
    of scope for this issue (would need a cancellation/re-booking flow).
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import BookingDetailOut, UpdateBookingRequest
from app.db.database import get_db
from app.db.models import Booking

router = APIRouter(prefix="/api", tags=["bookings"])

# Only these fields are staff-editable and therefore log-worthy — id,
# customer_id, status, created_at, and edit_log_json itself are never set
# via this endpoint.
_EDITABLE_FIELDS = ("room_type", "check_in", "check_out", "guests", "total_price")


@router.get("/bookings", response_model=list[BookingDetailOut])
def list_bookings(db: Session = Depends(get_db)) -> list[Booking]:
    return db.query(Booking).order_by(Booking.created_at.desc()).all()


@router.get("/bookings/{booking_id}", response_model=BookingDetailOut)
def get_booking(booking_id: int, db: Session = Depends(get_db)) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found")
    return booking


@router.patch("/bookings/{booking_id}", response_model=BookingDetailOut)
def update_booking(
    booking_id: int, payload: UpdateBookingRequest, db: Session = Depends(get_db)
) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found")
    if booking.status == "CONFIRMED":
        raise HTTPException(
            status_code=400, detail="Cannot edit a booking that has already been confirmed."
        )

    # Only fields the client actually sent — PATCH semantics, and it keeps
    # the edit log honest (no phantom "changed from X to X" entries for
    # fields the staff member never touched).
    updates = payload.model_dump(exclude_unset=True)
    log = json.loads(booking.edit_log_json)
    changed = False
    now = datetime.now(timezone.utc).isoformat()

    for field, new_value in updates.items():
        if field not in _EDITABLE_FIELDS:
            continue
        old_value = getattr(booking, field)
        if old_value == new_value:
            continue
        log.append(
            {"field": field, "old_value": str(old_value), "new_value": str(new_value), "at": now}
        )
        setattr(booking, field, new_value)
        changed = True

    if changed:
        booking.edit_log_json = json.dumps(log)
        if booking.status == "AI_DRAFTED":
            booking.status = "STAFF_REVIEWED"
        db.commit()
        db.refresh(booking)

    return booking


@router.post("/bookings/{booking_id}/confirm", response_model=BookingDetailOut)
def confirm_booking(booking_id: int, db: Session = Depends(get_db)) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail=f"Booking {booking_id} not found")
    if booking.status == "CONFIRMED":
        raise HTTPException(status_code=400, detail="Booking is already confirmed.")

    booking.status = "CONFIRMED"
    db.commit()
    db.refresh(booking)
    return booking
