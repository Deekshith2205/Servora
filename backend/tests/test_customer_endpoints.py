"""[RBAC] issues #182 (Customer: Ticket Status), #184 (Customer:
Customer Profile), #185 (Customer: Notifications), #186 (Customer role
restrictions).
"""
from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.db.models import Customer, Notification, Ticket
from app.main import app
from tests.rbac_headers import customer_headers, staff_headers

client = TestClient(app)


_email_counter = 0


def _seed_two_customers(db):
    global _email_counter
    _email_counter += 1
    c1 = Customer(name="Customer One", email=f"cust-endpoints-1-{_email_counter}@example.com")
    c2 = Customer(name="Customer Two", email=f"cust-endpoints-2-{_email_counter}@example.com")
    db.add_all([c1, c2])
    db.commit()
    db.refresh(c1)
    db.refresh(c2)
    return c1, c2


# --------------------------------------------------------------------- #
# #182 GET /api/tickets/mine
# --------------------------------------------------------------------- #


def test_customer_sees_only_their_own_tickets_never_anothers():
    db = SessionLocal()
    c1, c2 = _seed_two_customers(db)
    db.add(Ticket(customer_id=c1.id, category="order", subject="C1 ticket", message="m", status="open"))
    db.add(Ticket(customer_id=c2.id, category="order", subject="C2 ticket", message="m", status="open"))
    db.commit()

    resp1 = client.get("/api/tickets/mine", headers=customer_headers(c1.id))
    assert resp1.status_code == 200
    subjects1 = {t["subject"] for t in resp1.json()}
    assert "C1 ticket" in subjects1
    assert "C2 ticket" not in subjects1

    resp2 = client.get("/api/tickets/mine", headers=customer_headers(c2.id))
    subjects2 = {t["subject"] for t in resp2.json()}
    assert "C2 ticket" in subjects2
    assert "C1 ticket" not in subjects2


def test_tickets_mine_requires_a_customer_identity():
    """A Support Agent has no `view_own_tickets` grant at all — a real
    403. (Administrator legitimately DOES hold `view_own_tickets`, since
    its permission set is the real union of every other role's — see
    #199 — but has no real `customer_id`, so it gets an empty list
    rather than a 403; that case is covered in test_rbac_matrix.py.)"""
    db = SessionLocal()
    headers = staff_headers(db, "support_agent")
    resp = client.get("/api/tickets/mine", headers=headers)
    assert resp.status_code == 403


def test_tickets_mine_is_empty_not_an_error_for_a_customer_with_no_tickets():
    db = SessionLocal()
    c1, _ = _seed_two_customers(db)
    resp = client.get("/api/tickets/mine", headers=customer_headers(c1.id))
    assert resp.status_code == 200
    assert resp.json() == []


# --------------------------------------------------------------------- #
# #184 GET /api/records/customers/{id} — a Customer's own profile
# --------------------------------------------------------------------- #


def test_customer_can_view_their_own_profile():
    db = SessionLocal()
    c1, _ = _seed_two_customers(db)
    resp = client.get(f"/api/records/customers/{c1.id}", headers=customer_headers(c1.id))
    assert resp.status_code == 200
    assert resp.json()["id"] == c1.id


def test_customer_cannot_view_another_customers_profile():
    db = SessionLocal()
    c1, c2 = _seed_two_customers(db)
    resp = client.get(f"/api/records/customers/{c2.id}", headers=customer_headers(c1.id))
    assert resp.status_code == 403


# --------------------------------------------------------------------- #
# #185 GET /api/notifications — actor-scoped, not permission-gated
# --------------------------------------------------------------------- #


def test_customer_sees_only_their_own_notifications():
    db = SessionLocal()
    c1, c2 = _seed_two_customers(db)
    db.add(Notification(customer_id=c1.id, subject="For C1", body="m"))
    db.add(Notification(customer_id=c2.id, subject="For C2", body="m"))
    db.commit()

    resp = client.get("/api/notifications", headers=customer_headers(c1.id))
    assert resp.status_code == 200
    subjects = {n["subject"] for n in resp.json()}
    assert "For C1" in subjects
    assert "For C2" not in subjects


def test_staff_still_sees_all_notifications_unaffected_by_customer_scoping():
    """[RBAC] issue #185's own explicit requirement: staff callers
    (today's real caller, the Staff Dashboard booking drawer) are
    completely unaffected — no gate, no scoping."""
    db = SessionLocal()
    c1, c2 = _seed_two_customers(db)
    db.add(Notification(customer_id=c1.id, subject="Staff-visible C1", body="m"))
    db.add(Notification(customer_id=c2.id, subject="Staff-visible C2", body="m"))
    db.commit()

    headers = staff_headers(db, "support_agent")
    resp = client.get("/api/notifications", headers=headers)
    assert resp.status_code == 200
    subjects = {n["subject"] for n in resp.json()}
    assert {"Staff-visible C1", "Staff-visible C2"} <= subjects


def test_anonymous_actor_gets_the_unscoped_list_not_an_error():
    """An anonymous actor is neither staff nor a resolved Customer — the
    `actor.role == CUSTOMER` filter never applies, so this deliberately
    behaves like an unscoped (staff-shaped) caller rather than erroring.
    Documented here since it is a real, non-obvious edge of the
    actor-scoping design — `/api/notifications` has no permission gate
    at all (see #185's own scope note)."""
    resp = client.get("/api/notifications")
    assert resp.status_code == 200


# --------------------------------------------------------------------- #
# #186 Customer role restrictions — a Customer cannot reach staff-only
# surfaces, even ones with no natural "ownership" concept to fall back to.
# --------------------------------------------------------------------- #


def test_customer_cannot_reach_any_staff_only_surface():
    db = SessionLocal()
    c1, _ = _seed_two_customers(db)
    headers = customer_headers(c1.id)

    for path in [
        "/api/investigations",
        "/api/investigations/metrics/agents",
        "/api/analytics/summary",
        "/api/escalations",
        "/api/integrations/shopify/status",
        "/api/users",
        "/api/settings",
    ]:
        resp = client.get(path, headers=headers)
        assert resp.status_code == 403, f"customer should be forbidden at {path}, got {resp.status_code}"
