from datetime import datetime, timedelta
from fastapi.testclient import TestClient


from app.db.database import SessionLocal
from app.db.models import Ticket
from app.main import app


def test_analytics_summary_empty():
    db = SessionLocal()
    # Ensure tickets from seed are not empty, but we can clear them for this test
    db.query(Ticket).delete()
    db.commit()

    with TestClient(app) as client:
        response = client.get("/api/analytics/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert len(data["recurring_issues"]) == 0


def test_analytics_summary_clustering_shipping_delay():
    db = SessionLocal()
    db.query(Ticket).delete()
    db.commit()

    t1 = Ticket(
        customer_id=1, category="order", subject="Order delayed after shipping label creation", message="tracking number delayed", status="open"
    )
    t2 = Ticket(
        customer_id=1, category="order", subject="Tracking hasn't updated in days", message="tracking hasn't updated", status="open"
    )
    t3 = Ticket(
        customer_id=1, category="order", subject="Package stuck at fulfillment stage", message="package stuck fulfillment", status="open"
    )
    t4 = Ticket(
        customer_id=1, category="order", subject="Shipment hasn't moved for a week", message="shipment hasn't moved check", status="open"
    )
    t5 = Ticket(
        customer_id=1, category="billing", subject="Charged twice", message="I was charged twice", status="open"
    )
    db.add_all([t1, t2, t3, t4, t5])
    db.commit()

    with TestClient(app) as client:
        response = client.get("/api/analytics/summary")
        assert response.status_code == 200
        data = response.json()
        
        issues = data["recurring_issues"]
        assert len(issues) == 1
        
        cluster = issues[0]
        assert cluster["ticket_count"] == 4
        assert "stuck" in cluster["pattern"] or "tracking" in cluster["pattern"] or "shipment" in cluster["pattern"] or "delay" in cluster["pattern"]
        assert "delays" in cluster["root_cause_hypothesis"].lower()
        
        # Verify ticket IDs
        ticket_ids = cluster["ticket_ids"]
        assert t1.id in ticket_ids
        assert t2.id in ticket_ids
        assert t3.id in ticket_ids
        assert t4.id in ticket_ids
        assert t5.id not in ticket_ids


def test_analytics_isolated_ticket():
    db = SessionLocal()
    db.query(Ticket).delete()
    db.commit()

    t1 = Ticket(
        customer_id=1, category="account", subject="Forgot password", message="I cannot login", status="open"
    )
    db.add_all([t1])
    db.commit()

    with TestClient(app) as client:
        response = client.get("/api/analytics/summary")
        assert response.status_code == 200
        data = response.json()
        assert len(data["recurring_issues"]) == 0


def test_analytics_ignores_old_tickets():
    db = SessionLocal()
    db.query(Ticket).delete()
    db.commit()

    now = datetime.utcnow()
    t_old = Ticket(
        customer_id=1, category="order", subject="Tracking hasn't updated", message="My tracking is stuck", 
        status="open", created_at=now - timedelta(days=35)
    )
    t_new = Ticket(
        customer_id=1, category="order", subject="Tracking hasn't updated", message="My tracking is stuck", 
        status="open", created_at=now - timedelta(days=5)
    )
    
    db.add_all([t_old, t_new])
    db.commit()

    with TestClient(app) as client:
        response = client.get("/api/analytics/summary")
        assert response.status_code == 200
        data = response.json()
        assert len(data["recurring_issues"]) == 0


def test_analytics_clustering_is_deterministic():
    db = SessionLocal()
    db.query(Ticket).delete()
    db.commit()

    t1 = Ticket(
        customer_id=1, category="order", subject="Order delayed after shipping label creation", message="tracking number delayed", status="open"
    )
    t2 = Ticket(
        customer_id=1, category="order", subject="Tracking hasn't updated in days", message="tracking hasn't updated", status="open"
    )
    t3 = Ticket(
        customer_id=1, category="order", subject="Package stuck at fulfillment stage", message="package stuck fulfillment", status="open"
    )
    
    db.add_all([t1, t2, t3])
    db.commit()

    with TestClient(app) as client:
        response1 = client.get("/api/analytics/summary")
        response2 = client.get("/api/analytics/summary")
        
        data1 = response1.json()
        data2 = response2.json()
        
        assert len(data1["recurring_issues"]) == 1
        cluster1 = data1["recurring_issues"][0]
        cluster2 = data2["recurring_issues"][0]
        
        assert cluster1["ticket_count"] == cluster2["ticket_count"]
        assert cluster1["pattern"] == cluster2["pattern"]
        assert cluster1["root_cause_hypothesis"] == cluster2["root_cause_hypothesis"]
        assert cluster1["ticket_ids"] == cluster2["ticket_ids"]
