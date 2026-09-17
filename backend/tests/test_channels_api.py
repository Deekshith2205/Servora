"""[Omnichannel] issue #135 — Channel status management.

Uses the shared session-wide test DB (conftest.py already seeded the 5
real channels via seed_if_empty() before any test module is imported),
same convention test_health.py's module-level `TestClient(app)` relies
on — no fixture needed here since nothing in this file mutates the
Customer/Ticket tables other tests depend on.

[RBAC]: PATCH /api/channels/{id} is now gated to `manage_integrations`
(Administrator only, issue #202) — every write test below sends a real
Administrator identity header. GET stays open, unaffected.
"""
from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.db.models import Channel
from app.main import app
from tests.rbac_headers import staff_headers

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
    with SessionLocal() as db:
        whatsapp_id = db.query(Channel).filter(Channel.key == "whatsapp").first().id
        headers = staff_headers(db, "administrator")
        db.close()

        resp = client.patch(f"/api/channels/{whatsapp_id}", json={"status": "active"}, headers=headers)
        assert resp.status_code == 400
        assert "not been configured" in resp.json()["detail"]

        # Confirmed unchanged, not silently left in some in-between state.
        db = SessionLocal()
        assert db.get(Channel, whatsapp_id).status == "not_configured"
        db.close()


def test_can_toggle_an_already_configured_channel_inactive_and_back():
    with SessionLocal() as db:
        live_chat_id = db.query(Channel).filter(Channel.key == "live_chat").first().id
        headers = staff_headers(db, "administrator")
        db.close()

        resp = client.patch(f"/api/channels/{live_chat_id}", json={"status": "inactive"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "inactive"

        resp = client.patch(f"/api/channels/{live_chat_id}", json={"status": "active"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"


def test_rejects_an_invalid_status_value():
    with SessionLocal() as db:
        live_chat_id = db.query(Channel).filter(Channel.key == "live_chat").first().id
        headers = staff_headers(db, "administrator")
        db.close()

        resp = client.patch(f"/api/channels/{live_chat_id}", json={"status": "bogus"}, headers=headers)
        assert resp.status_code == 400


def test_returns_404_for_an_unknown_channel_id():
    with SessionLocal() as db:
        headers = staff_headers(db, "administrator")
        db.close()

        resp = client.patch("/api/channels/999999", json={"status": "inactive"}, headers=headers)
        assert resp.status_code == 404


def test_patch_without_permission_is_a_real_403():
    """[RBAC] issue #202: a Support Agent (no `manage_integrations`)
    gets a real 403 attempting to change a channel's status."""
    with SessionLocal() as db:
        live_chat_id = db.query(Channel).filter(Channel.key == "live_chat").first().id
        headers = staff_headers(db, "support_agent")
        db.close()

        resp = client.patch(f"/api/channels/{live_chat_id}", json={"status": "inactive"}, headers=headers)
        assert resp.status_code == 403
