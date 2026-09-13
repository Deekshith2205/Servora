"""Tests for [EXPLAIN] issue #95's read-only record-preview endpoints
(app/api/records.py, app/api/kb.py::get_kb_article) — backs the Evidence
Explorer's inline preview when clicking an order/customer/ticket/KB-
article evidence reference.
"""
from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.db.models import Customer, KBArticle, Order, Ticket
from app.main import app

_email_counter = 0


def _seed_customer(db):
    global _email_counter
    _email_counter += 1
    customer = Customer(name="Records Test Customer", email=f"records-{_email_counter}@example.com", phone="555-0100", tier="vip")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def test_get_order_returns_the_real_row():
    db = SessionLocal()
    customer = _seed_customer(db)
    order = Order(customer_id=customer.id, product="Wireless Headphones", amount=129.99, status="shipped", payment_status="paid")
    db.add(order)
    db.commit()
    db.refresh(order)

    with TestClient(app) as client:
        resp = client.get(f"/api/records/orders/{order.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["product"] == "Wireless Headphones"
    assert body["customer_id"] == customer.id
    assert body["status"] == "shipped"


def test_get_order_404_for_unknown_id():
    with TestClient(app) as client:
        resp = client.get("/api/records/orders/999999")
    assert resp.status_code == 404


def test_get_customer_returns_the_real_row():
    db = SessionLocal()
    customer = _seed_customer(db)

    with TestClient(app) as client:
        resp = client.get(f"/api/records/customers/{customer.id}")

    assert resp.status_code == 200
    assert resp.json()["tier"] == "vip"


def test_get_ticket_returns_the_real_row():
    db = SessionLocal()
    customer = _seed_customer(db)
    # Explicit, deliberately-out-of-range id: several other test files
    # (test_analytics.py, test_kb_api.py) call `db.query(Ticket).delete()`
    # on this SAME shared file-based test DB (see conftest.py) to isolate
    # their own scenarios — since SQLite reuses low ROWIDs once a table is
    # emptied, letting this insert autoincrement normally risked colliding
    # with a ticket_id another test file's Investigation row already
    # claims (Investigation.ticket_id is UNIQUE). A high explicit id
    # sidesteps that shared-state hazard entirely rather than depending on
    # exact test execution order across files.
    ticket = Ticket(id=900001, customer_id=customer.id, category="billing", subject="Test ticket", message="m", sentiment="neutral", urgency=5, status="closed")
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    with TestClient(app) as client:
        resp = client.get(f"/api/records/tickets/{ticket.id}")

    assert resp.status_code == 200
    assert resp.json()["subject"] == "Test ticket"


def test_tickets_resolved_endpoint_is_not_shadowed_by_the_new_records_router():
    """Real risk this test guards against: a naive /api/tickets/{id}
    route would have shadowed the existing literal /api/tickets/resolved
    route depending on router registration order. records.py deliberately
    uses /api/records/tickets/{id} instead — this proves the original
    endpoint still works exactly as before."""
    with TestClient(app) as client:
        resp = client.get("/api/tickets/resolved")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_kb_article_returns_the_real_row():
    db = SessionLocal()
    article = KBArticle(title="Test Policy", body="Body text", tags="test")
    db.add(article)
    db.commit()
    db.refresh(article)

    with TestClient(app) as client:
        resp = client.get(f"/api/kb-articles/{article.id}")

    assert resp.status_code == 200
    assert resp.json()["title"] == "Test Policy"


def test_get_kb_article_404_for_unknown_id():
    with TestClient(app) as client:
        resp = client.get("/api/kb-articles/999999")
    assert resp.status_code == 404
