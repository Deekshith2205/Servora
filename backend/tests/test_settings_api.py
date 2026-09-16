"""[RBAC] issue #204 — Admin: System Configuration.

`app/api/settings.py` — a real, DB-backed key-value settings surface,
Administrator only.
"""
from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.main import app
from tests.rbac_headers import staff_headers

client = TestClient(app)


def _admin_headers():
    db = SessionLocal()
    headers = staff_headers(db, "administrator")
    db.close()
    return headers


def test_list_settings_returns_the_real_seeded_rows():
    resp = client.get("/api/settings", headers=_admin_headers())
    assert resp.status_code == 200
    keys = {s["key"] for s in resp.json()}
    assert {"demo_mode", "default_escalation_confidence_threshold"} <= keys


def test_list_settings_without_permission_is_a_real_403():
    db = SessionLocal()
    headers = staff_headers(db, "manager")
    resp = client.get("/api/settings", headers=headers)
    assert resp.status_code == 403


def test_update_setting_changes_the_real_value():
    headers = _admin_headers()
    resp = client.patch("/api/settings/demo_mode", json={"value": "false"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["value"] == "false"

    # Restore, so this test doesn't leak state into other tests on the
    # same shared file-based test DB.
    client.patch("/api/settings/demo_mode", json={"value": "true"}, headers=headers)


def test_update_setting_404_for_unknown_key():
    resp = client.patch("/api/settings/not_a_real_setting", json={"value": "x"}, headers=_admin_headers())
    assert resp.status_code == 404


def test_update_setting_without_permission_is_a_real_403():
    db = SessionLocal()
    headers = staff_headers(db, "support_agent")
    resp = client.patch("/api/settings/demo_mode", json={"value": "false"}, headers=headers)
    assert resp.status_code == 403

    # Confirmed unchanged.
    admin_headers = staff_headers(db, "administrator")
    current = client.get("/api/settings", headers=admin_headers).json()
    demo_mode = next(s for s in current if s["key"] == "demo_mode")
    assert demo_mode["value"] == "true"
