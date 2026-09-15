"""[Omnichannel] issue #135 — Channel status management.

Uses the shared session-wide test DB (conftest.py already seeded the 5
real channels via seed_if_empty() before any test module is imported),
same convention test_health.py's module-level `TestClient(app)` relies
on — no fixture needed here since nothing in this file mutates the
Customer/Ticket tables other tests depend on.
"""
from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.db.models import Channel
from app.main import app

client = TestClient(app)


def test_list_channels_returns_all_five_seeded_channels():
    resp = client.get("/api/channels")
    assert resp.status_code == 200
    body = resp.json()
    assert {c["key"] for c in body} == {"live_chat", "email", "whatsapp", "instagram", "messenger"}
    assert len(body) == 5


def test_list_channels_reports_real_status_values():
    resp = client.get("/api/channels")
    by_key = {c["key"]: c for c in resp.json()}
    assert by_key["live_chat"]["status"] == "active"
    assert by_key["whatsapp"]["status"] == "not_configured"


def test_cannot_activate_a_not_configured_channel():
    db = SessionLocal()
    whatsapp_id = db.query(Channel).filter(Channel.key == "whatsapp").first().id
    db.close()

    resp = client.patch(f"/api/channels/{whatsapp_id}", json={"status": "active"})
    assert resp.status_code == 400
    assert "not been configured" in resp.json()["detail"]

    # Confirmed unchanged, not silently left in some in-between state.
    db = SessionLocal()
    assert db.get(Channel, whatsapp_id).status == "not_configured"
    db.close()


def test_can_toggle_an_already_configured_channel_inactive_and_back():
    db = SessionLocal()
    live_chat_id = db.query(Channel).filter(Channel.key == "live_chat").first().id
    db.close()

    resp = client.patch(f"/api/channels/{live_chat_id}", json={"status": "inactive"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "inactive"

    resp = client.patch(f"/api/channels/{live_chat_id}", json={"status": "active"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_rejects_an_invalid_status_value():
    db = SessionLocal()
    live_chat_id = db.query(Channel).filter(Channel.key == "live_chat").first().id
    db.close()

    resp = client.patch(f"/api/channels/{live_chat_id}", json={"status": "bogus"})
    assert resp.status_code == 400


def test_returns_404_for_an_unknown_channel_id():
    resp = client.patch("/api/channels/999999", json={"status": "inactive"})
    assert resp.status_code == 404
