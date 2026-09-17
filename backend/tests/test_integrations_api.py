"""Tests for Settings -> Integrations: app/api/integrations.py.

Monkeypatches `app.api.integrations.test_connection` (the real Shopify
credential check) at the API-test boundary — same "mock the external
call, exercise the real endpoint" convention as every other API test in
this codebase (e.g. test_health.py mocking `app.orchestrator.classify`).
app/services/shopify_service.py's OWN real HTTP/retry logic is already
covered directly in tests/test_shopify_service.py.

[RBAC]: every Shopify endpoint here is now gated to `manage_integrations`
(Administrator only, issue #202) — every call sends a real
Administrator identity header.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.db.models import ShopifyIntegration
from app.main import app
from app.services.shopify_service import ShopifyAPIError
from tests.rbac_headers import staff_headers


def _clear_integrations(db):
    """Each test starts from a clean slate on the shared test DB (same
    convention `test_analytics.py`/`test_kb_api.py` already use for
    Ticket) — the "most recent row wins" convention in
    shopify_service._get_integration() means a stale row from an earlier
    test would otherwise leak into this one."""
    db.query(ShopifyIntegration).delete()
    db.commit()


def test_status_reports_never_connected_when_no_row_exists():
    with SessionLocal() as db:
        _clear_integrations(db)
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            resp = client.get("/api/integrations/shopify/status", headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["connected"] is False
        assert body["status"] == "never_connected"
        assert "access_token" not in body  # never leak the credential shape at all


def test_connect_verifies_real_credentials_before_saving():
    with SessionLocal() as db:
        _clear_integrations(db)
        headers = staff_headers(db, "administrator")

        with patch("app.api.integrations.test_connection", return_value={"name": "Test Shop"}):
            with TestClient(app) as client:
                resp = client.post("/api/integrations/shopify/connect", json={
                    "store_url": "test-shop.myshopify.com", "access_token": "shpat_real_looking_token",
                }, headers=headers)

        assert resp.status_code == 200
        body = resp.json()
        assert body["connected"] is True
        assert body["status"] == "connected"
        assert body["store_url"] == "test-shop.myshopify.com"
        assert "access_token" not in body


def test_connect_never_saves_as_connected_when_credentials_are_bad():
    with SessionLocal() as db:
        _clear_integrations(db)
        headers = staff_headers(db, "administrator")

        with patch("app.api.integrations.test_connection", side_effect=ShopifyAPIError("bad creds", status_code=401)):
            with TestClient(app) as client:
                resp = client.post("/api/integrations/shopify/connect", json={
                    "store_url": "test-shop.myshopify.com", "access_token": "shpat_invalid",
                }, headers=headers)

        assert resp.status_code == 400

        # The real, decisive assertion: no row was persisted as "connected".
        status_resp_db = SessionLocal()
        integration = status_resp_db.query(ShopifyIntegration).order_by(ShopifyIntegration.id.desc()).first()
        assert integration is None or integration.status != "connected"


def test_status_reflects_a_real_connected_row_and_masks_the_token():
    with SessionLocal() as db:
        _clear_integrations(db)
        db.add(ShopifyIntegration(store_url="test-shop.myshopify.com", access_token="shpat_super_secret", status="connected"))
        db.commit()
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            resp = client.get("/api/integrations/shopify/status", headers=headers)

        body = resp.json()
        assert body["connected"] is True
        assert body["store_url"] == "test-shop.myshopify.com"
        assert "shpat_super_secret" not in resp.text  # the raw token must never appear anywhere in the response


def test_disconnect_clears_the_stored_credential():
    with SessionLocal() as db:
        _clear_integrations(db)
        db.add(ShopifyIntegration(store_url="test-shop.myshopify.com", access_token="shpat_super_secret", status="connected"))
        db.commit()
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            resp = client.post("/api/integrations/shopify/disconnect", headers=headers)

        assert resp.status_code == 200
        assert resp.json()["connected"] is False

        check_db = SessionLocal()
        integration = check_db.query(ShopifyIntegration).order_by(ShopifyIntegration.id.desc()).first()
        assert integration.status == "disconnected"
        assert integration.access_token == ""  # the live credential is gone, not just the status flag


def test_disconnect_with_nothing_connected_is_a_clean_400():
    with SessionLocal() as db:
        _clear_integrations(db)
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            resp = client.post("/api/integrations/shopify/disconnect", headers=headers)

        assert resp.status_code == 400


def test_status_reports_a_real_connected_orders_count():
    """Reuses the existing evidence architecture for this count — see
    app/api/integrations.py::_connected_orders_count()'s own docstring —
    rather than a separate counter. Proven here by writing a real
    InvestigationStep with a shopify_order evidence_ref and confirming
    the count reflects it."""
    import json

    from app.db.models import Investigation, InvestigationStep, Ticket

    with SessionLocal() as db:
        _clear_integrations(db)
        db.add(ShopifyIntegration(store_url="test-shop.myshopify.com", access_token="shpat_x", status="connected"))
        db.commit()

        # Explicit out-of-range id — same shared-test-DB ROWID-collision
        # reason documented in test_records_api.py::test_get_ticket_returns_the_real_row.
        ticket = Ticket(id=900201, customer_id=1, category="order", subject="t", message="m", sentiment="neutral", urgency=5, status="resolved")
        db.add(ticket)
        db.commit()
        investigation = Investigation(ticket_id=ticket.id, customer_id=1, status="resolved")
        db.add(investigation)
        db.commit()
        db.add(InvestigationStep(
            investigation_id=investigation.id, step_number=1, agent_name="order_specialist", action="a", status="completed",
            evidence_refs_json=json.dumps([{"type": "shopify_order", "ref_id": 1002, "label": "Shopify #1002"}]),
        ))
        db.commit()
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            resp = client.get("/api/integrations/shopify/status", headers=headers)

        assert resp.json()["connected_orders_count"] >= 1


def test_shopify_status_without_permission_is_a_real_403():
    """[RBAC] issue #202: a Support Agent (no `manage_integrations`)
    cannot even check Shopify's connection status."""
    with SessionLocal() as db:
        headers = staff_headers(db, "support_agent")

        with TestClient(app) as client:
            resp = client.get("/api/integrations/shopify/status", headers=headers)

        assert resp.status_code == 403
