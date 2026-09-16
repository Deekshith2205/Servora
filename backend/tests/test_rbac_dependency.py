"""[RBAC] issues #175 (permission middleware), #176 (route
authorization), #177 (API authorization), #180 (unauthorized access
handling) — `app/auth/dependency.py`'s real enforcement mechanics,
tested directly through a real HTTP round-trip via `GET /api/auth/me`
(itself unguarded, so it can resolve ANY actor state including
anonymous) and a couple of already-gated real routes.
"""
from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.db.models import Customer, User
from app.main import app
from tests.rbac_headers import customer_headers, staff_headers

client = TestClient(app)


def test_no_headers_resolves_to_anonymous():
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] is None
    assert body["customer_id"] is None
    assert body["user_id"] is None


def test_unrecognized_role_string_resolves_to_anonymous():
    resp = client.get("/api/auth/me", headers={"X-Servora-Role": "super_admin"})
    assert resp.json()["role"] is None


def test_customer_role_with_no_customer_id_header_resolves_to_anonymous():
    resp = client.get("/api/auth/me", headers={"X-Servora-Role": "customer"})
    assert resp.json()["role"] is None


def test_customer_role_with_a_nonexistent_customer_id_resolves_to_anonymous():
    resp = client.get("/api/auth/me", headers={"X-Servora-Role": "customer", "X-Servora-Customer-Id": "999999"})
    assert resp.json()["role"] is None


def test_customer_role_with_a_real_customer_id_resolves_correctly():
    db = SessionLocal()
    customer = Customer(name="Dependency Test Customer", email="dep-test-customer@example.com")
    db.add(customer)
    db.commit()
    db.refresh(customer)

    resp = client.get("/api/auth/me", headers=customer_headers(customer.id))
    body = resp.json()
    assert body["role"] == "customer"
    assert body["customer_id"] == customer.id
    assert body["user_id"] is None


def test_staff_role_with_no_user_id_header_resolves_to_anonymous():
    resp = client.get("/api/auth/me", headers={"X-Servora-Role": "administrator"})
    assert resp.json()["role"] is None


def test_staff_role_with_a_nonexistent_user_id_resolves_to_anonymous():
    resp = client.get("/api/auth/me", headers={"X-Servora-Role": "administrator", "X-Servora-User-Id": "999999"})
    assert resp.json()["role"] is None


def test_staff_role_header_claim_is_never_trusted_over_the_real_user_row():
    """[RBAC] issue #176's own security requirement: the resolved
    `User` row's own `role` column is authoritative, never the
    `X-Servora-Role` header's claim — a Support Agent's real user_id
    cannot escalate to administrator just by sending a different role
    header alongside the same, real user_id."""
    db = SessionLocal()
    user = db.query(User).filter(User.role == "support_agent").first()
    assert user is not None  # seeded

    resp = client.get("/api/auth/me", headers={
        "X-Servora-Role": "administrator",  # a spoofed claim
        "X-Servora-User-Id": str(user.id),  # but a real support_agent's id
    })
    body = resp.json()
    assert body["role"] == "support_agent"  # the real row wins, not the header
    assert body["user_id"] == user.id


def test_a_valid_staff_role_string_routes_to_the_staff_lookup_even_if_it_understates_the_real_role():
    """The role header only needs to be A valid staff role string to
    route into the staff-lookup branch at all — the actual grant is
    always the resolved row's own role, confirmed the other direction
    too (an Administrator's real user_id, claimed as `support_agent`,
    still resolves as administrator)."""
    db = SessionLocal()
    user = db.query(User).filter(User.role == "administrator").first()
    assert user is not None

    resp = client.get("/api/auth/me", headers={
        "X-Servora-Role": "support_agent",
        "X-Servora-User-Id": str(user.id),
    })
    assert resp.json()["role"] == "administrator"


def test_get_permissions_is_public_reference_data_not_gated():
    """`GET /api/auth/permissions` is deliberately ungated — permission
    NAMES are not per-user data."""
    resp = client.get("/api/auth/permissions")
    assert resp.status_code == 200
    body = resp.json()
    assert "administrator" in body
    assert "manage_users" in body["administrator"]


def test_unauthorized_access_returns_a_generic_403_never_leaking_which_permission_was_missing():
    """[RBAC] issue #180: a real 403 with a generic detail message —
    never enumerating the actual permission name, which would be a
    permission-discovery side channel."""
    resp = client.get("/api/users")  # anonymous, manage_users required
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert "manage_users" not in detail
    assert detail  # a real, non-empty message, not a blank body


def test_require_any_permission_grants_access_if_any_one_permission_matches():
    """[RBAC] issue #194: a Manager reaches
    /api/investigations/metrics/agents via `view_analytics` alone, even
    without `view_investigation_board`."""
    db = SessionLocal()
    headers = staff_headers(db, "manager")
    resp = client.get("/api/investigations/metrics/agents", headers=headers)
    assert resp.status_code == 200


def test_require_any_permission_also_grants_access_via_the_other_permission():
    db = SessionLocal()
    headers = staff_headers(db, "support_agent")  # has view_investigation_board, not view_analytics — still passes
    resp = client.get("/api/investigations/metrics/agents", headers=headers)
    assert resp.status_code == 200


def test_require_any_permission_403s_if_neither_permission_matches():
    resp = client.get("/api/investigations/metrics/agents", headers=customer_headers(1))
    assert resp.status_code == 403
