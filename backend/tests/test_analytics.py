from datetime import datetime, timedelta
from fastapi.testclient import TestClient


from app.db.database import SessionLocal
from app.db.models import Ticket
from app.main import app
from tests.rbac_headers import staff_headers

# [RBAC] issue #193/#198: GET /api/analytics/summary is now gated to
# `view_analytics` (Manager/Administrator) — every call below sends a
# real Administrator identity header.


def test_analytics_summary_empty():
    with SessionLocal() as db:
        # Ensure tickets from seed are not empty, but we can clear them for this test
        db.query(Ticket).delete()
        db.commit()
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            response = client.get("/api/analytics/summary", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert len(data["recurring_issues"]) == 0


def test_analytics_summary_clustering_shipping_delay():
    with SessionLocal() as db:
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
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            response = client.get("/api/analytics/summary", headers=headers)
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
    with SessionLocal() as db:
        db.query(Ticket).delete()
        db.commit()

        t1 = Ticket(
            customer_id=1, category="account", subject="Forgot password", message="I cannot login", status="open"
        )
        db.add_all([t1])
        db.commit()
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            response = client.get("/api/analytics/summary", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data["recurring_issues"]) == 0


def test_analytics_ignores_old_tickets():
    with SessionLocal() as db:
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
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            response = client.get("/api/analytics/summary", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data["recurring_issues"]) == 0


def test_analytics_clustering_is_deterministic():
    with SessionLocal() as db:
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
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            response1 = client.get("/api/analytics/summary", headers=headers)
            response2 = client.get("/api/analytics/summary", headers=headers)

            data1 = response1.json()
            data2 = response2.json()

            assert len(data1["recurring_issues"]) == 1
            cluster1 = data1["recurring_issues"][0]
            cluster2 = data2["recurring_issues"][0]

            assert cluster1["ticket_count"] == cluster2["ticket_count"]
            assert cluster1["pattern"] == cluster2["pattern"]
            assert cluster1["root_cause_hypothesis"] == cluster2["root_cause_hypothesis"]
            assert cluster1["ticket_ids"] == cluster2["ticket_ids"]


def test_analytics_summary_without_permission_is_a_real_403():
    """[RBAC] issue #193/#198: a Support Agent (no `view_analytics`)
    gets a real 403 on the analytics summary."""
    with SessionLocal() as db:
        headers = staff_headers(db, "support_agent")

        with TestClient(app) as client:
            response = client.get("/api/analytics/summary", headers=headers)

        assert response.status_code == 403


    # ---------------------------------------------------------------------------
    # Issue #16: churn signals + trend
    # ---------------------------------------------------------------------------


def test_churn_signal_below_threshold_is_not_flagged():
    with SessionLocal() as db:
        db.query(Ticket).delete()
        db.commit()

        db.add(Ticket(customer_id=1, category="order", subject="Where is my order", message="?", status="open"))
        db.commit()
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            response = client.get("/api/analytics/summary", headers=headers)
            assert response.status_code == 200
            assert response.json()["churn_signals"] == []


def test_churn_signal_medium_risk_at_two_unresolved_tickets():
    with SessionLocal() as db:
        db.query(Ticket).delete()
        db.commit()

        db.add_all([
            Ticket(customer_id=1, category="order", subject="a", message="a", status="open"),
            Ticket(customer_id=1, category="billing", subject="b", message="b", status="escalated"),
        ])
        db.commit()
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            data = client.get("/api/analytics/summary", headers=headers).json()

        signals = data["churn_signals"]
        assert len(signals) == 1
        assert signals[0]["customer_id"] == 1
        assert signals[0]["unresolved_ticket_count"] == 2
        assert signals[0]["risk_level"] == "medium"


def test_churn_signal_high_risk_at_four_unresolved_tickets():
    with SessionLocal() as db:
        db.query(Ticket).delete()
        db.commit()

        db.add_all([
            Ticket(customer_id=1, category="order", subject=f"t{i}", message="m", status="open") for i in range(4)
        ])
        db.commit()
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            data = client.get("/api/analytics/summary", headers=headers).json()

        signals = data["churn_signals"]
        assert len(signals) == 1
        assert signals[0]["risk_level"] == "high"
        assert signals[0]["unresolved_ticket_count"] == 4


def test_churn_signal_resolved_tickets_dont_count():
    with SessionLocal() as db:
        db.query(Ticket).delete()
        db.commit()

        db.add_all([
            Ticket(customer_id=1, category="order", subject="a", message="a", status="resolved"),
            Ticket(customer_id=1, category="order", subject="b", message="b", status="resolved"),
            Ticket(customer_id=1, category="order", subject="c", message="c", status="resolved"),
        ])
        db.commit()
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            data = client.get("/api/analytics/summary", headers=headers).json()

        assert data["churn_signals"] == []


def test_trend_is_zero_padded_across_the_window():
    with SessionLocal() as db:
        db.query(Ticket).delete()
        db.commit()

        db.add(Ticket(customer_id=1, category="order", subject="a", message="a", status="open"))
        db.commit()
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            data = client.get("/api/analytics/summary", headers=headers).json()

        trend = data["trend"]
        assert len(trend) == 30  # exactly 30 calendar days
        assert sum(day["count"] for day in trend) == 1  # exactly the one ticket just created
        assert trend[-1]["count"] == 1  # most recent day (today) has it
        # dates are in ascending order
        assert [d["date"] for d in trend] == sorted(d["date"] for d in trend)


    # ---------------------------------------------------------------------------
    # Issue #62: resolution rate, escalation rate, sentiment trend, confidence distribution
    # ---------------------------------------------------------------------------


def test_rates_with_mixed_tickets():
    with SessionLocal() as db:
        db.query(Ticket).delete()
        db.commit()

        # 6 resolved, 2 escalated, 5 open
        for i in range(6):
            db.add(Ticket(customer_id=1, category="order", subject="a", message="a", status="resolved"))
        for i in range(2):
            db.add(Ticket(customer_id=1, category="order", subject="a", message="a", status="escalated"))
        for i in range(5):
            db.add(Ticket(customer_id=1, category="order", subject="a", message="a", status="open"))

        db.commit()
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            data = client.get("/api/analytics/summary", headers=headers).json()

        # denominator should be processed tickets (resolved + escalated) = 8
        res_rate = data["resolution_rate"]
        esc_rate = data["escalation_rate"]

        assert res_rate["resolved"] == 6
        assert res_rate["total"] == 8
        assert res_rate["rate"] == 0.75

        assert esc_rate["escalated"] == 2
        assert esc_rate["total"] == 8
        assert esc_rate["rate"] == 0.25


def test_rates_with_only_open_tickets():
    with SessionLocal() as db:
        db.query(Ticket).delete()
        db.commit()

        db.add(Ticket(customer_id=1, category="order", subject="a", message="a", status="open"))
        db.commit()
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            data = client.get("/api/analytics/summary", headers=headers).json()

        # no processed tickets
        res_rate = data["resolution_rate"]
        esc_rate = data["escalation_rate"]

        assert res_rate["resolved"] == 0
        assert res_rate["total"] == 0
        assert res_rate["rate"] == 0.0

        assert esc_rate["escalated"] == 0
        assert esc_rate["total"] == 0
        assert esc_rate["rate"] == 0.0


def test_old_resolved_tickets_are_excluded_from_rates():
    with SessionLocal() as db:
        db.query(Ticket).delete()
        db.commit()

        now = datetime.utcnow()
        t_old = Ticket(customer_id=1, category="order", subject="a", message="a", status="resolved", created_at=now - timedelta(days=35))
        t_new = Ticket(customer_id=1, category="order", subject="a", message="a", status="resolved", created_at=now - timedelta(days=5))
        db.add_all([t_old, t_new])
        db.commit()
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            data = client.get("/api/analytics/summary", headers=headers).json()

        res_rate = data["resolution_rate"]
        assert res_rate["resolved"] == 1
        assert res_rate["total"] == 1
        assert res_rate["rate"] == 1.0


def test_sentiment_trend():
    with SessionLocal() as db:
        db.query(Ticket).delete()
        db.commit()

        # mix of valid sentiment, empty sentiment, None sentiment
        db.add_all([
            Ticket(customer_id=1, category="order", subject="a", message="a", sentiment="positive"),
            Ticket(customer_id=1, category="order", subject="a", message="a", sentiment="negative"),
            Ticket(customer_id=1, category="order", subject="a", message="a", sentiment="negative"),
            Ticket(customer_id=1, category="order", subject="a", message="a", sentiment=""),
            Ticket(customer_id=1, category="order", subject="a", message="a", sentiment=None),
            Ticket(customer_id=1, category="order", subject="a", message="a", sentiment="invalid_sentiment"),
        ])
        db.commit()
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            data = client.get("/api/analytics/summary", headers=headers).json()

        sentiment_trend = data["sentiment_trend"]
        assert len(sentiment_trend) == 30
        today_bucket = sentiment_trend[-1]

        assert today_bucket["positive"] == 1
        assert today_bucket["negative"] == 2
        assert today_bucket["neutral"] == 0

        # sum of all positives across the trend should be exactly 1
        assert sum(day["positive"] for day in sentiment_trend) == 1
        assert sum(day["negative"] for day in sentiment_trend) == 2


def test_confidence_distribution_ignores_nulls():
    with SessionLocal() as db:
        db.query(Ticket).delete()
        db.commit()

        # low, moderate, high, null
        db.add_all([
            Ticket(customer_id=1, category="order", subject="a", message="a", confidence=0.20),
            Ticket(customer_id=1, category="order", subject="a", message="a", confidence=0.70),
            Ticket(customer_id=1, category="order", subject="a", message="a", confidence=0.90),
            Ticket(customer_id=1, category="order", subject="a", message="a", confidence=0.99),
            Ticket(customer_id=1, category="order", subject="a", message="a", confidence=None),
        ])
        db.commit()
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            data = client.get("/api/analytics/summary", headers=headers).json()

        dist = data["confidence_distribution"]
        assert dist["low"] == 1
        assert dist["moderate"] == 1
        assert dist["high"] == 2
        assert dist["total"] == 4


def test_confidence_distribution_boundaries():
    with SessionLocal() as db:
        db.query(Ticket).delete()
        db.commit()

        db.add_all([
            Ticket(customer_id=1, category="order", subject="low", message="a", confidence=0.59),
            Ticket(customer_id=1, category="order", subject="mod1", message="a", confidence=0.60),
            Ticket(customer_id=1, category="order", subject="mod2", message="a", confidence=0.79),
            Ticket(customer_id=1, category="order", subject="high", message="a", confidence=0.80),
        ])
        db.commit()
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            data = client.get("/api/analytics/summary", headers=headers).json()

        dist = data["confidence_distribution"]
        assert dist["low"] == 1
        assert dist["moderate"] == 2
        assert dist["high"] == 1
        assert dist["total"] == 4


def test_analytics_30_day_cutoff_boundaries():
    with SessionLocal() as db:
        db.query(Ticket).delete()
        db.commit()

        now = datetime.utcnow()
        # 30 calendar days including today = today + 29 previous days.
        # Cutoff is midnight of (now - 29 days).
        t_exactly_30_days_ago = Ticket(customer_id=1, category="order", subject="30d ago", message="a", status="resolved", created_at=now - timedelta(days=30))
        t_start_of_29d_ago = Ticket(customer_id=1, category="order", subject="29d ago midnight", message="a", status="resolved", created_at=datetime(now.year, now.month, now.day) - timedelta(days=29))
        t_today = Ticket(customer_id=1, category="order", subject="today", message="a", status="resolved", created_at=now)

        db.add_all([t_exactly_30_days_ago, t_start_of_29d_ago, t_today])
        db.commit()
        headers = staff_headers(db, "administrator")

        with TestClient(app) as client:
            data = client.get("/api/analytics/summary", headers=headers).json()

        # t_exactly_30_days_ago is excluded, others included
        res_rate = data["resolution_rate"]
        assert res_rate["total"] == 2


def test_manager_analytics_permission():
    """[RBAC] issue #195: Manager has view_analytics and can access resolution_rate/escalation_rate."""
    with SessionLocal() as db:
        headers = staff_headers(db, "manager")
        with TestClient(app) as client:
            response = client.get("/api/analytics/summary", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert "resolution_rate" in data
            assert "escalation_rate" in data
