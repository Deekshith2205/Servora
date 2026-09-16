"""[RBAC] issue #200 — Admin: User Management.

`app/api/users.py` — the first genuinely new admin-only surface this
epic adds. Administrator-only throughout.
"""
from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.db.models import User
from app.main import app
from tests.rbac_headers import staff_headers

client = TestClient(app)


def _admin_headers():
    db = SessionLocal()
    headers = staff_headers(db, "administrator")
    db.close()
    return headers


def test_list_users_returns_real_seeded_staff():
    resp = client.get("/api/users", headers=_admin_headers())
    assert resp.status_code == 200
    roles = {u["role"] for u in resp.json()}
    assert {"support_agent", "manager", "administrator"} <= roles
    # Never a password/credential field of any kind — this codebase has none.
    assert all("password" not in u for u in resp.json())


def test_list_users_without_permission_is_a_real_403():
    db = SessionLocal()
    headers = staff_headers(db, "support_agent")
    resp = client.get("/api/users", headers=headers)
    assert resp.status_code == 403


def test_create_user_inserts_a_real_row():
    headers = _admin_headers()
    resp = client.post("/api/users", json={
        "name": "New Support Rep", "email": "new-support-rep@example.com", "role": "support_agent",
    }, headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "New Support Rep"
    assert body["role"] == "support_agent"

    saved = SessionLocal().get(User, body["id"])
    assert saved is not None
    assert saved.email == "new-support-rep@example.com"


def test_create_user_rejects_a_customer_role():
    """A Customer identity is a `Customer` row, never a `User` row —
    creating a `User` with role="customer" would be a nonsensical
    identity this codebase's own model split forbids."""
    resp = client.post("/api/users", json={
        "name": "Bad", "email": "bad-role-user@example.com", "role": "customer",
    }, headers=_admin_headers())
    assert resp.status_code == 400


def test_create_user_rejects_a_duplicate_email():
    headers = _admin_headers()
    payload = {"name": "Dup One", "email": "dup-user-test@example.com", "role": "manager"}
    first = client.post("/api/users", json=payload, headers=headers)
    assert first.status_code == 200

    second = client.post("/api/users", json=payload, headers=headers)
    assert second.status_code == 400


def test_create_user_without_permission_is_a_real_403():
    db = SessionLocal()
    headers = staff_headers(db, "manager")
    resp = client.post("/api/users", json={
        "name": "Nope", "email": "nope-user@example.com", "role": "support_agent",
    }, headers=headers)
    assert resp.status_code == 403

    # And confirmed no row was actually inserted.
    assert db.query(User).filter(User.email == "nope-user@example.com").first() is None


def test_update_user_changes_name_and_role():
    headers = _admin_headers()
    create = client.post("/api/users", json={
        "name": "Before Update", "email": "update-user-test@example.com", "role": "support_agent",
    }, headers=headers)
    user_id = create.json()["id"]

    resp = client.patch(f"/api/users/{user_id}", json={"name": "After Update", "role": "manager"}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "After Update"
    assert body["role"] == "manager"


def test_update_user_404_for_unknown_id():
    resp = client.patch("/api/users/999999", json={"name": "x"}, headers=_admin_headers())
    assert resp.status_code == 404


def test_update_user_without_permission_is_a_real_403():
    db = SessionLocal()
    headers = staff_headers(db, "support_agent")
    resp = client.patch("/api/users/1", json={"name": "x"}, headers=headers)
    assert resp.status_code == 403
