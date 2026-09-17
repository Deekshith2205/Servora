"""Tests for GET /api/notifications (issue #21)."""
from app.db.database import SessionLocal
from app.db.models import Notification
from app.main import app
from fastapi.testclient import TestClient

_email_counter = 0


def _seed_customer(db):
    from app.db.models import Customer

    global _email_counter
    _email_counter += 1
    customer = Customer(name="Test Customer", email=f"notif-api-test-{_email_counter}@example.com")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def test_list_notifications_returns_seeded_row():
    with SessionLocal() as db:
        customer = _seed_customer(db)
        notification = Notification(customer_id=customer.id, subject="Update to your booking #1", body="test body")
        db.add(notification)
        db.commit()
        db.refresh(notification)

        with TestClient(app) as client:
            resp = client.get("/api/notifications")

        assert resp.status_code == 200
        ids = [n["id"] for n in resp.json()]
        assert notification.id in ids


def test_patch_booking_notification_is_also_visible_via_list_endpoint():
    """End-to-end: editing a booking through the real API produces a
    notification that a second, independent call can see."""
    with SessionLocal() as db:
        customer = _seed_customer(db)
        from app.db.models import Booking

        booking = Booking(
            customer_id=customer.id, room_type="deluxe", check_in="2026-12-01",
            check_out="2026-12-04", guests=2, total_price=417.0, status="AI_DRAFTED",
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)

        with TestClient(app) as client:
            patch_resp = client.patch(f"/api/bookings/{booking.id}", json={"guests": 3})
            list_resp = client.get("/api/notifications")

        notification_id = patch_resp.json()["notification"]["id"]
        ids = [n["id"] for n in list_resp.json()]
        assert notification_id in ids
