"""Tests for issue #21: app/services/notifications.py and GET /api/notifications."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Booking, Customer, Notification
from app.services.notifications import (
    build_booking_edit_diff_message,
    notify_customer_of_booking_edit,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _seed(db):
    customer = Customer(name="Dana Lee", email="dana@example.com")
    db.add(customer)
    db.flush()
    booking = Booking(
        customer_id=customer.id, room_type="deluxe", check_in="2026-12-01",
        check_out="2026-12-04", guests=2, total_price=417.0, status="AI_DRAFTED",
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return customer, booking


def test_build_diff_message_single_field():
    entries = [{"field": "room_type", "old_value": "suite", "new_value": "deluxe", "at": "now"}]
    msg = build_booking_edit_diff_message(entries)
    assert msg == "Your booking was updated: your room type changed from suite to deluxe."


def test_build_diff_message_formats_price_as_currency():
    entries = [{"field": "total_price", "old_value": "229.0", "new_value": "417.0", "at": "now"}]
    msg = build_booking_edit_diff_message(entries)
    assert "$229.00 to $417.00" in msg


def test_build_diff_message_multiple_fields_joined():
    entries = [
        {"field": "room_type", "old_value": "suite", "new_value": "deluxe", "at": "now"},
        {"field": "guests", "old_value": "1", "new_value": "2", "at": "now"},
    ]
    msg = build_booking_edit_diff_message(entries)
    assert "room type changed from suite to deluxe" in msg
    assert "number of guests changed from 1 to 2" in msg
    assert msg.count(";") == 1  # exactly two clauses joined once


def test_build_diff_message_empty_entries_is_generic():
    assert build_booking_edit_diff_message([]) == "Your booking was updated."


def test_notify_creates_a_notification_row(db_session):
    customer, booking = _seed(db_session)
    entries = [{"field": "room_type", "old_value": "suite", "new_value": "deluxe", "at": "now"}]

    notification = notify_customer_of_booking_edit(db_session, customer.id, booking, entries)

    assert notification is not None
    assert notification.customer_id == customer.id
    assert f"booking #{booking.id}" in notification.subject
    assert "room type" in notification.body

    # Actually persisted.
    assert db_session.query(Notification).count() == 1


def test_notify_with_no_entries_returns_none_and_creates_nothing(db_session):
    customer, booking = _seed(db_session)

    notification = notify_customer_of_booking_edit(db_session, customer.id, booking, [])

    assert notification is None
    assert db_session.query(Notification).count() == 0
