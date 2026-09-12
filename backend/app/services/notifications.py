"""Customer notifications. Implements issue #21 "[P4] Customer notification
on booking edit" — see docs/ARCHITECTURE.md's booking state machine ("any
edit made after AI_DRAFTED triggers a customer notification with a diff of
what changed") and app/db/models.py::Booking.edit_log_json (issue #20).

Deliberately mocked, not a real email/SMS send — same convention as every
other external dependency in this codebase (app/tools/mock_tools.py mocks
orders/refunds/room lookups; there is no real payment processor either).
The issue text suggests "the Gmail connector already available in this
workspace" as the cheapest real-delivery path, but that connector belongs
to the chat session that built this feature, not to the deployed FastAPI
app — the backend would need its own Gmail OAuth credentials/consent flow
to send mail as part of its own runtime behavior, which is a distinct,
larger integration than writing this function. Recording a `Notification`
row here (rather than only logging) keeps this genuinely useful — it's a
durable, queryable "a notification was sent" record the Staff Dashboard
surfaces and tests can assert against — while making the "not a real send"
boundary explicit so swapping in a real provider later is a self-contained
follow-up that doesn't change any caller of `notify_customer_of_booking_edit`.
"""
import logging

from sqlalchemy.orm import Session

from app.db.models import Booking, Notification

_log = logging.getLogger(__name__)

# Human-readable labels for the fields Booking.edit_log_json can record —
# matches app/api/bookings.py's _EDITABLE_FIELDS.
_FIELD_LABELS = {
    "room_type": "room type",
    "check_in": "check-in date",
    "check_out": "check-out date",
    "guests": "number of guests",
    "total_price": "total price",
}


def build_booking_edit_diff_message(new_entries: list[dict]) -> str:
    """Compose a plain-language diff from just the entries this edit added
    (not the booking's whole edit history) — e.g. "your room type changed
    from suite to deluxe; your total price changed from $229.00 to
    $417.00." Takes the new log entries directly (rather than a `Booking`
    and re-deriving them) so a caller that just appended several entries in
    one PATCH can report exactly those, not the full history.
    """
    parts = []
    for entry in new_entries:
        label = _FIELD_LABELS.get(entry["field"], entry["field"])
        old, new = entry["old_value"], entry["new_value"]
        if entry["field"] == "total_price":
            old, new = f"${float(old):.2f}", f"${float(new):.2f}"
        parts.append(f"your {label} changed from {old} to {new}")

    if not parts:
        return "Your booking was updated."

    return "Your booking was updated: " + "; ".join(parts) + "."


def notify_customer_of_booking_edit(
    db: Session, customer_id: int, booking: Booking, new_entries: list[dict]
) -> Notification | None:
    """Record a notification for a booking edit. Returns None (and logs a
    warning) rather than raising if `new_entries` is empty — nothing
    actually changed, so there is nothing to notify about; the caller
    (app/api/bookings.py) already only calls this when `changed` is True,
    so an empty list here would itself be a bug worth surfacing in logs.
    """
    if not new_entries:
        _log.warning(
            "notify_customer_of_booking_edit called with no new_entries for booking %s",
            booking.id,
        )
        return None

    message = build_booking_edit_diff_message(new_entries)
    notification = Notification(
        customer_id=customer_id,
        subject=f"Update to your booking #{booking.id}",
        body=message,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    _log.info("Notification queued for customer %s: %s", customer_id, message)
    return notification
