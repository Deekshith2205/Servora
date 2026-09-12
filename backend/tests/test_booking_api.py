"""Tests for issue #18's API surface: POST /api/booking.

Uses the real app + real DB via TestClient (`with TestClient(app) as
client:` — required so the lifespan actually runs, see conftest.py's own
note). Only the Booking Agent's LLM call is mocked — same pattern as
tests/test_kb_api.py for issue #17.
"""
from app.agents.booking import BookingAgentResult
from app.db.database import SessionLocal
from app.db.models import Booking, Customer
from app.llm import LLMError
from app.main import app
from fastapi.testclient import TestClient


_counter = 0


def _seed_customer(db):
    # Tests here share the one file-based test DB (see conftest.py) within a
    # single pytest run, so a fixed email would collide across tests via the
    # `email` unique constraint — give each call its own.
    global _counter
    _counter += 1
    customer = Customer(name="Test Customer", email=f"booking-api-test-{_counter}@example.com")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def test_booking_chat_404_for_unknown_customer():
    with TestClient(app) as client:
        resp = client.post("/api/booking", json={"customer_id": 999999, "messages": [
            {"role": "user", "content": "hi"}
        ]})
    assert resp.status_code == 404


def test_booking_chat_returns_reply_and_no_booking_mid_conversation(monkeypatch):
    db = SessionLocal()
    customer = _seed_customer(db)

    monkeypatch.setattr(
        "app.api.booking.run_booking_agent",
        lambda db, customer_id, messages: BookingAgentResult(
            reply="What dates would you like?", booking=None, used_tools=[]
        ),
    )

    with TestClient(app) as client:
        resp = client.post("/api/booking", json={
            "customer_id": customer.id,
            "messages": [{"role": "user", "content": "I want a deluxe room"}],
        })

    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"] == "What dates would you like?"
    assert body["booking"] is None


def test_booking_chat_returns_booking_once_created(monkeypatch):
    db = SessionLocal()
    customer = _seed_customer(db)
    booking = Booking(
        customer_id=customer.id, room_type="deluxe", check_in="2026-12-01",
        check_out="2026-12-04", guests=2, total_price=417.0, status="AI_DRAFTED",
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    monkeypatch.setattr(
        "app.api.booking.run_booking_agent",
        lambda db, customer_id, messages: BookingAgentResult(
            reply="Booked! Pending staff review.", booking=booking, used_tools=["create_draft_booking"]
        ),
    )

    with TestClient(app) as client:
        resp = client.post("/api/booking", json={
            "customer_id": customer.id,
            "messages": [
                {"role": "user", "content": "deluxe, Dec 1-4, 2 guests"},
                {"role": "assistant", "content": "That's $417, confirm?"},
                {"role": "user", "content": "yes"},
            ],
        })

    assert resp.status_code == 200
    body = resp.json()
    assert body["booking"]["status"] == "AI_DRAFTED"
    assert body["booking"]["total_price"] == 417.0


def test_booking_chat_llm_error_becomes_502_not_an_unhandled_500(monkeypatch):
    """Regression guard for the CORS/opaque-error class of bug fixed in
    issue #17 (llm.py's bare-TypeError gap) — this endpoint has no
    best-effort degrade path (the booking reply IS the response), so an
    LLMError must become a readable HTTPException, not propagate raw."""
    db = SessionLocal()
    customer = _seed_customer(db)

    def _raise(db, customer_id, messages):
        raise LLMError("Anthropic API key is missing or invalid.")

    monkeypatch.setattr("app.api.booking.run_booking_agent", _raise)

    with TestClient(app) as client:
        resp = client.post("/api/booking", json={
            "customer_id": customer.id,
            "messages": [{"role": "user", "content": "hi"}],
        })

    assert resp.status_code == 502
    assert "API key" in resp.json()["detail"]
