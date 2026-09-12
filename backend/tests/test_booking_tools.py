"""Tests for the booking tools (issue #18): check_availability and
create_draft_booking, plus the Anthropic tool-registry wiring around them.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Booking, Customer, Room
from app.tools.booking_tools import (
    BOOKING_TOOL_SCHEMAS,
    build_booking_tool_registry,
    check_availability,
    create_draft_booking,
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


def _seed_rooms(db):
    db.add_all([
        Room(room_type="standard", price_per_night=89.0, total_count=10),
        Room(room_type="deluxe", price_per_night=139.0, total_count=6),
        Room(room_type="suite", price_per_night=229.0, total_count=2),
    ])
    customer = Customer(name="Ann Carter", email="ann@example.com")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


# ---------------------------------------------------------------------------
# check_availability
# ---------------------------------------------------------------------------


def test_check_availability_happy_path_computes_nights_and_price(db_session):
    _seed_rooms(db_session)
    result = check_availability(db_session, "deluxe", "2026-10-01", "2026-10-04", 2)
    assert result["available"] is True
    assert result["nights"] == 3
    assert result["total_price"] == 417.0  # 3 * 139.0
    assert result["available_rooms"] == 6


def test_check_availability_unknown_room_type(db_session):
    _seed_rooms(db_session)
    result = check_availability(db_session, "penthouse", "2026-10-01", "2026-10-04", 2)
    assert result["available"] is False
    assert "Unknown room type" in result["reason"]


def test_check_availability_invalid_date_format(db_session):
    _seed_rooms(db_session)
    result = check_availability(db_session, "standard", "10/01/2026", "2026-10-04", 1)
    assert result["available"] is False
    assert "YYYY-MM-DD" in result["reason"]


def test_check_availability_checkout_before_checkin(db_session):
    _seed_rooms(db_session)
    result = check_availability(db_session, "standard", "2026-10-05", "2026-10-04", 1)
    assert result["available"] is False
    assert "after" in result["reason"]


def test_check_availability_no_rooms_left_for_overlapping_dates(db_session):
    customer = _seed_rooms(db_session)
    # Suite has only 2 total — book both for an overlapping range.
    db_session.add_all([
        Booking(customer_id=customer.id, room_type="suite", check_in="2026-11-01",
                check_out="2026-11-05", guests=2, total_price=916.0, status="AI_DRAFTED"),
        Booking(customer_id=customer.id, room_type="suite", check_in="2026-11-02",
                check_out="2026-11-06", guests=2, total_price=916.0, status="CONFIRMED"),
    ])
    db_session.commit()

    result = check_availability(db_session, "suite", "2026-11-03", "2026-11-04", 1)
    assert result["available"] is False
    assert "no suite rooms are available" in result["reason"].lower()


def test_check_availability_ignores_cancelled_bookings(db_session):
    customer = _seed_rooms(db_session)
    # Both suites "booked" but cancelled — should not count against availability.
    db_session.add_all([
        Booking(customer_id=customer.id, room_type="suite", check_in="2026-11-01",
                check_out="2026-11-05", guests=2, total_price=916.0, status="cancelled"),
        Booking(customer_id=customer.id, room_type="suite", check_in="2026-11-02",
                check_out="2026-11-06", guests=2, total_price=916.0, status="cancelled"),
    ])
    db_session.commit()

    result = check_availability(db_session, "suite", "2026-11-03", "2026-11-04", 1)
    assert result["available"] is True
    assert result["available_rooms"] == 2


def test_check_availability_non_overlapping_dates_are_unaffected(db_session):
    customer = _seed_rooms(db_session)
    db_session.add_all([
        Booking(customer_id=customer.id, room_type="suite", check_in="2026-11-01",
                check_out="2026-11-05", guests=2, total_price=916.0, status="AI_DRAFTED"),
        Booking(customer_id=customer.id, room_type="suite", check_in="2026-11-05",
                check_out="2026-11-06", guests=2, total_price=229.0, status="AI_DRAFTED"),
    ])
    db_session.commit()

    # A range that starts exactly when the first booking ends should be free.
    result = check_availability(db_session, "suite", "2026-11-06", "2026-11-08", 1)
    assert result["available"] is True


# ---------------------------------------------------------------------------
# create_draft_booking
# ---------------------------------------------------------------------------


def test_create_draft_booking_success(db_session):
    customer = _seed_rooms(db_session)
    result = create_draft_booking(db_session, customer.id, "standard", "2026-12-01", "2026-12-03", 2)
    assert result["created"] is True
    booking = result["booking"]
    assert booking.id is not None
    assert booking.status == "AI_DRAFTED"
    assert booking.total_price == 178.0  # 2 nights * 89.0

    # Actually persisted.
    fetched = db_session.get(Booking, booking.id)
    assert fetched is not None
    assert fetched.customer_id == customer.id


def test_create_draft_booking_rejects_when_unavailable(db_session):
    customer = _seed_rooms(db_session)
    result = create_draft_booking(db_session, customer.id, "penthouse", "2026-12-01", "2026-12-03", 2)
    assert result["created"] is False
    assert "Unknown room type" in result["reason"]
    assert db_session.query(Booking).count() == 0


# ---------------------------------------------------------------------------
# Tool registry wiring
# ---------------------------------------------------------------------------


def test_booking_tool_schemas_have_expected_names():
    names = {s["name"] for s in BOOKING_TOOL_SCHEMAS}
    assert names == {"check_availability", "create_draft_booking"}


def test_registry_check_availability_handler(db_session):
    customer = _seed_rooms(db_session)
    schemas, handlers, created = build_booking_tool_registry(db_session, customer.id)
    result = handlers["check_availability"](
        {"room_type": "standard", "check_in": "2026-12-01", "check_out": "2026-12-03", "guests": 1}
    )
    assert result["available"] is True
    assert created == []  # only create_draft_booking appends here


def test_registry_create_draft_booking_handler_populates_created_list(db_session):
    customer = _seed_rooms(db_session)
    schemas, handlers, created = build_booking_tool_registry(db_session, customer.id)
    result = handlers["create_draft_booking"](
        {"room_type": "standard", "check_in": "2026-12-01", "check_out": "2026-12-03", "guests": 1}
    )
    assert result["created"] is True
    assert isinstance(result["booking"], dict)  # serialized, not a raw ORM object
    assert len(created) == 1
    assert created[0].customer_id == customer.id


def test_registry_create_draft_booking_handler_does_not_append_on_failure(db_session):
    customer = _seed_rooms(db_session)
    schemas, handlers, created = build_booking_tool_registry(db_session, customer.id)
    result = handlers["create_draft_booking"](
        {"room_type": "penthouse", "check_in": "2026-12-01", "check_out": "2026-12-03", "guests": 1}
    )
    assert result["created"] is False
    assert created == []
