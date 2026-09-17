"""Tests for [EXPLAIN] issue #95's read-only record-preview endpoints
(app/api/records.py, app/api/kb.py::get_kb_article) — backs the Evidence
Explorer's inline preview when clicking an order/customer/ticket/KB-
article evidence reference.
"""
from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.db.models import Customer, KBArticle, Order, Ticket
from app.main import app
from tests.rbac_headers import staff_headers

# [RBAC] issue #188/#218: each get-real-row test below sends a real
# Administrator identity header (`view_evidence` covers all three
# record types). The "unknown id" 404 tests are unaffected — the lookup
# raises before the permission check. `/kb-articles/{id}` and the
# Shopify record endpoints are untouched by this RBAC batch.

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
    with SessionLocal() as db:
        customer = _seed_customer(db)
        order = Order(customer_id=customer.id, product="Wireless Headphones", amount=129.99, status="shipped", payment_status="paid")
        db.add(order)
        db.commit()
        db.refresh(order)
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            resp = client.get(f"/api/records/orders/{order.id}", headers=headers)

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
    with SessionLocal() as db:
        customer = _seed_customer(db)
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            resp = client.get(f"/api/records/customers/{customer.id}", headers=headers)

        assert resp.status_code == 200
        assert resp.json()["tier"] == "vip"


def test_get_customer_reports_zero_previous_tickets_and_no_risk_level_when_clean():
    """[Explainability #123]: `risk_level` is None (not a fabricated
    "low") for a customer with no concerning ticket history — matches
    analytics.py's compute_churn_signals(), which omits such customers
    entirely rather than reporting a floor value."""
    with SessionLocal() as db:
        customer = _seed_customer(db)
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            resp = client.get(f"/api/records/customers/{customer.id}", headers=headers)

        body = resp.json()
        assert body["previous_tickets_count"] == 0
        assert body["risk_level"] is None


def test_get_customer_reports_previous_tickets_count_and_risk_level():
    with SessionLocal() as db:
        customer = _seed_customer(db)
        # Same deliberately-out-of-range id pattern as test_get_ticket_returns_the_real_row
        # below, for the same shared-test-DB ROWID-collision reason.
        for i, status in enumerate(["escalated", "open", "resolved"]):
            db.add(Ticket(
                id=900100 + i, customer_id=customer.id, category="billing", subject=f"t{i}",
                message="m", sentiment="neutral", urgency=5, status=status,
            ))
        db.commit()
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            resp = client.get(f"/api/records/customers/{customer.id}", headers=headers)

        body = resp.json()
        assert body["previous_tickets_count"] == 3  # all 3, regardless of status
        # 2 unresolved (escalated + open) meets CHURN_MEDIUM_THRESHOLD (2) but
        # not CHURN_HIGH_THRESHOLD (4) -> "medium".
        assert body["risk_level"] == "medium"


def test_get_customer_includes_channel_history():
    """[Omnichannel] issue #157: a customer with multiple tickets across
    channels gets them correctly mapped, ordered newest-first, and distinct
    channels_used."""
    with SessionLocal() as db:
        customer = _seed_customer(db)
    
        # Add tickets with explicit timing to verify newest-first
        from datetime import datetime, timedelta
        now = datetime.utcnow()
    
        t1 = Ticket(
            customer_id=customer.id, subject="First", message="m", 
            channel_key="email", status="resolved", created_at=now - timedelta(days=2)
        )
        t2 = Ticket(
            customer_id=customer.id, subject="Second", message="m", 
            channel_key="whatsapp", status="open", created_at=now - timedelta(days=1)
        )
        # Testing legacy null/empty channel defaults to live_chat logic
        t3 = Ticket(
            customer_id=customer.id, subject="Third", message="m", 
            channel_key=None, status="escalated", created_at=now
        )
        t4 = Ticket(
            customer_id=customer.id, subject="Fourth", message="m", 
            channel_key="whatsapp", status="open", created_at=now + timedelta(days=1)
        )
    
        db.add_all([t1, t2, t3, t4])
        db.commit()
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            resp = client.get(f"/api/records/customers/{customer.id}", headers=headers)

        assert resp.status_code == 200
        body = resp.json()

        # 1. Distinct channels
        assert body["channels_used"] == ["whatsapp", "live_chat", "email"]
    
        # 2. History ordered newest first
        history = body["conversation_history"]
        assert len(history) == 4
        assert history[0]["subject"] == "Fourth"
        assert history[1]["subject"] == "Third"
        assert history[2]["subject"] == "Second"
        assert history[3]["subject"] == "First"
    
        # 3. Channel attribution including fallback
        assert history[0]["channel"] == "whatsapp"
        assert history[1]["channel"] == "live_chat"
        assert history[2]["channel"] == "whatsapp"
        assert history[3]["channel"] == "email"


def test_get_customer_404_for_unknown_id():
    with TestClient(app) as client:
        resp = client.get("/api/records/customers/999999")
    assert resp.status_code == 404


def test_get_ticket_returns_the_real_row():
    with SessionLocal() as db:
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
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            resp = client.get(f"/api/records/tickets/{ticket.id}", headers=headers)

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
    with SessionLocal() as db:
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


def test_support_agent_customer_history():
    """[RBAC] issue #191: Support Agent has view_customer_conversations/view_evidence and can fetch ANY customer profile + history."""
    with SessionLocal() as db:
        customer = _seed_customer(db)
    
        # Add a ticket to ensure history populates correctly
        t1 = Ticket(
            customer_id=customer.id, category="billing", subject="Support Test",
            message="test msg", sentiment="neutral", urgency=5, status="resolved",
        )
        db.add(t1)
        db.commit()
    
        headers = staff_headers(db, "support_agent")

        with TestClient(app) as client:
            resp = client.get(f"/api/records/customers/{customer.id}", headers=headers)
    
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == customer.id
    
        # Verify history is present
        history = body.get("conversation_history", [])
        assert len(history) == 1
        assert history[0]["id"] == t1.id
