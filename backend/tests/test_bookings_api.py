"""Tests for issue #20's API surface: GET/PATCH /api/bookings and
POST /api/bookings/{id}/confirm.

Uses the real app + real DB via TestClient (`with TestClient(app) as
client:` — required so the lifespan actually runs, see conftest.py).
"""
import json

from app.db.database import SessionLocal
from app.db.models import Booking, Customer
from app.main import app
from fastapi.testclient import TestClient

_email_counter = 0


def _seed_booking(db, **overrides):
    global _email_counter
    _email_counter += 1
    customer = Customer(name="Test Customer", email=f"bookings-api-test-{_email_counter}@example.com")
    db.add(customer)
    db.commit()
    db.refresh(customer)

    defaults = dict(
        customer_id=customer.id, room_type="deluxe", check_in="2026-12-01",
        check_out="2026-12-04", guests=2, total_price=417.0, status="AI_DRAFTED",
    )
    defaults.update(overrides)
    booking = Booking(**defaults)
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


def test_get_booking_404_for_unknown_id():
    with TestClient(app) as client:
        resp = client.get("/api/bookings/999999")
    assert resp.status_code == 404


def test_get_booking_returns_empty_edit_log_for_a_fresh_draft():
    db = SessionLocal()
    booking = _seed_booking(db)

    with TestClient(app) as client:
        resp = client.get(f"/api/bookings/{booking.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "AI_DRAFTED"
    assert body["edit_log"] == []


def test_list_bookings_includes_seeded_booking():
    db = SessionLocal()
    booking = _seed_booking(db)

    with TestClient(app) as client:
        resp = client.get("/api/bookings")

    assert resp.status_code == 200
    ids = [b["id"] for b in resp.json()]
    assert booking.id in ids


def test_patch_booking_changes_field_logs_it_bumps_status_and_notifies():
    db = SessionLocal()
    booking = _seed_booking(db)

    with TestClient(app) as client:
        resp = client.patch(f"/api/bookings/{booking.id}", json={"room_type": "standard"})

    assert resp.status_code == 200
    body = resp.json()
    updated = body["booking"]
    assert updated["room_type"] == "standard"
    assert updated["status"] == "STAFF_REVIEWED"  # bumped from AI_DRAFTED
    assert len(updated["edit_log"]) == 1
    entry = updated["edit_log"][0]
    assert entry["field"] == "room_type"
    assert entry["old_value"] == "deluxe"
    assert entry["new_value"] == "standard"

    # Issue #21: this edit must have produced a notification with a diff.
    assert body["notification"] is not None
    assert body["notification"]["customer_id"] == booking.customer_id
    assert "room type" in body["notification"]["body"]
    assert "deluxe" in body["notification"]["body"]
    assert "standard" in body["notification"]["body"]

    # Actually persisted.
    db.refresh(booking)
    assert booking.room_type == "standard"
    assert json.loads(booking.edit_log_json) == updated["edit_log"]


def test_patch_booking_with_no_actual_change_does_not_log_bump_status_or_notify():
    db = SessionLocal()
    booking = _seed_booking(db)

    with TestClient(app) as client:
        resp = client.patch(f"/api/bookings/{booking.id}", json={"room_type": "deluxe"})  # same value

    assert resp.status_code == 200
    body = resp.json()
    assert body["booking"]["status"] == "AI_DRAFTED"  # unchanged — nothing was actually edited
    assert body["booking"]["edit_log"] == []
    assert body["notification"] is None  # nothing changed — nothing to notify about


def test_patch_booking_logs_multiple_changed_fields_and_notifies_both():
    db = SessionLocal()
    booking = _seed_booking(db)

    with TestClient(app) as client:
        resp = client.patch(
            f"/api/bookings/{booking.id}",
            json={"room_type": "suite", "guests": 4, "check_in": "2026-12-01"},  # check_in unchanged
        )

    body = resp.json()
    changed_fields = {e["field"] for e in body["booking"]["edit_log"]}
    assert changed_fields == {"room_type", "guests"}  # check_in excluded — same value

    # One notification covering both real changes, not two separate ones.
    assert "room type" in body["notification"]["body"]
    assert "number of guests" in body["notification"]["body"]


def test_patch_booking_rejected_once_confirmed():
    db = SessionLocal()
    booking = _seed_booking(db, status="CONFIRMED")

    with TestClient(app) as client:
        resp = client.patch(f"/api/bookings/{booking.id}", json={"room_type": "standard"})

    assert resp.status_code == 400


def test_confirm_booking_transitions_status():
    db = SessionLocal()
    booking = _seed_booking(db, status="STAFF_REVIEWED")

    with TestClient(app) as client:
        resp = client.post(f"/api/bookings/{booking.id}/confirm")

    assert resp.status_code == 200
    assert resp.json()["status"] == "CONFIRMED"


def test_confirm_booking_works_directly_from_ai_drafted():
    """Not every draft needs an edit before confirming."""
    db = SessionLocal()
    booking = _seed_booking(db, status="AI_DRAFTED")

    with TestClient(app) as client:
        resp = client.post(f"/api/bookings/{booking.id}/confirm")

    assert resp.status_code == 200
    assert resp.json()["status"] == "CONFIRMED"


def test_confirm_booking_rejected_if_already_confirmed():
    db = SessionLocal()
    booking = _seed_booking(db, status="CONFIRMED")

    with TestClient(app) as client:
        resp = client.post(f"/api/bookings/{booking.id}/confirm")

    assert resp.status_code == 400


def test_confirm_booking_404_for_unknown_id():
    with TestClient(app) as client:
        resp = client.post("/api/bookings/999999/confirm")
    assert resp.status_code == 404
