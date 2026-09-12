"""Tests for the Booking Agent (issue #18). Same mocked-Anthropic-client
pattern as tests/test_specialists.py — the DB and tool registry are real,
only the LLM response sequence is scripted, so a passing test proves a
`Booking` row with status AI_DRAFTED is actually created, not just that the
right function got called.
"""
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.booking import run_booking_agent
from app.db.database import Base
from app.db.models import Booking, Customer, Room


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
    db.add(Room(room_type="deluxe", price_per_night=139.0, total_count=6))
    customer = Customer(name="Priya Shah", email="priya@example.com")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def _tool_use(id_, name, input_):
    block = MagicMock()
    block.type, block.id, block.name, block.input = "tool_use", id_, name, input_
    return block


def _text(text):
    block = MagicMock()
    block.type, block.text = "text", text
    return block


def _response(content, stop_reason):
    resp = MagicMock()
    resp.content, resp.stop_reason = content, stop_reason
    return resp


@patch("app.llm._client", None)
def test_run_booking_agent_completes_a_full_booking(db_session):
    customer = _seed(db_session)

    responses = [
        _response(
            [_tool_use("t1", "check_availability", {
                "room_type": "deluxe", "check_in": "2026-12-01", "check_out": "2026-12-04", "guests": 2,
            })],
            "tool_use",
        ),
        _response(
            [_text("A deluxe room for Dec 1-4 (3 nights) comes to $417.00 total. Shall I book it?")],
            "end_turn",
        ),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("app.llm.get_client", return_value=mock_client):
        result = run_booking_agent(
            db_session,
            customer.id,
            [{"role": "user", "content": "I'd like a deluxe room Dec 1-4 for 2 guests"}],
        )

    assert result.used_tools == ["check_availability"]
    assert result.booking is None  # not confirmed yet — no booking created
    assert "417" in result.reply


@patch("app.llm._client", None)
def test_run_booking_agent_creates_booking_on_confirmation(db_session):
    customer = _seed(db_session)

    responses = [
        _response(
            [_tool_use("t1", "create_draft_booking", {
                "room_type": "deluxe", "check_in": "2026-12-01", "check_out": "2026-12-04", "guests": 2,
            })],
            "tool_use",
        ),
        _response(
            [_text("Booked! Your deluxe room for Dec 1-4 is drafted and pending hotel staff review.")],
            "end_turn",
        ),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("app.llm.get_client", return_value=mock_client):
        result = run_booking_agent(
            db_session,
            customer.id,
            [
                {"role": "user", "content": "deluxe, Dec 1-4, 2 guests"},
                {"role": "assistant", "content": "That's $417.00 total, shall I book it?"},
                {"role": "user", "content": "yes, please book it"},
            ],
        )

    assert result.used_tools == ["create_draft_booking"]
    assert result.booking is not None
    assert result.booking.status == "AI_DRAFTED"
    assert result.booking.customer_id == customer.id

    # Actually persisted — the acceptance criteria this issue cares about.
    fetched = db_session.get(Booking, result.booking.id)
    assert fetched is not None
    assert fetched.total_price == 417.0
    assert fetched.status == "AI_DRAFTED"
