"""[Omnichannel] issue #158 — Channel performance metrics.

compute_channel_metrics() extends the EXISTING analytics API with a
real per-channel breakdown, via a genuine SQL GROUP BY — not a new
analytics system. The acceptance criteria's own consistency check:
real counts per channel must sum to the same total the existing
(channel-agnostic) ticket count already reports.
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.analytics import compute_channel_metrics
from app.db.database import Base
from app.db.models import Customer, Ticket


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _seed_customer(db):
    customer = Customer(name="Metrics Customer", email="metrics-channel@example.com", tier="standard")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def _ticket(customer_id, channel_key, status):
    return Ticket(
        customer_id=customer_id,
        category="order",
        subject="s",
        message="m",
        sentiment="neutral",
        urgency=3,
        status=status,
        channel_key=channel_key,
    )


def test_channel_metrics_reports_real_counts_per_channel(db_session):
    customer = _seed_customer(db_session)
    db_session.add_all([
        _ticket(customer.id, "live_chat", "resolved"),
        _ticket(customer.id, "live_chat", "resolved"),
        _ticket(customer.id, "whatsapp", "escalated"),
        _ticket(customer.id, "email", "open"),
    ])
    db_session.commit()

    metrics = compute_channel_metrics(db_session, datetime.utcnow() - timedelta(days=30))
    by_channel = {m["channel"]: m for m in metrics}

    assert by_channel["live_chat"]["total"] == 2
    assert by_channel["live_chat"]["resolved"] == 2
    assert by_channel["whatsapp"]["total"] == 1
    assert by_channel["whatsapp"]["escalated"] == 1
    assert by_channel["email"]["total"] == 1
    assert by_channel["email"]["open"] == 1


def test_channel_metrics_sum_matches_the_channel_agnostic_total(db_session):
    """The issue's own acceptance criteria: real counts per channel sum
    to the same total the existing channel-agnostic analytics report."""
    customer = _seed_customer(db_session)
    db_session.add_all([
        _ticket(customer.id, "live_chat", "resolved"),
        _ticket(customer.id, "whatsapp", "escalated"),
        _ticket(customer.id, "whatsapp", "open"),
        _ticket(customer.id, "instagram", "resolved"),
        _ticket(customer.id, "messenger", "resolved"),
    ])
    db_session.commit()

    cutoff = datetime.utcnow() - timedelta(days=30)
    metrics = compute_channel_metrics(db_session, cutoff)

    channel_sum = sum(m["total"] for m in metrics)
    real_total = db_session.query(Ticket).filter(Ticket.created_at >= cutoff).count()

    assert channel_sum == real_total == 5


def test_channel_metrics_excludes_tickets_outside_the_cutoff_window(db_session):
    customer = _seed_customer(db_session)
    old_ticket = _ticket(customer.id, "live_chat", "resolved")
    old_ticket.created_at = datetime.utcnow() - timedelta(days=60)
    db_session.add(old_ticket)
    db_session.commit()

    metrics = compute_channel_metrics(db_session, datetime.utcnow() - timedelta(days=30))
    assert metrics == []


def test_channel_metrics_returns_empty_list_with_no_tickets(db_session):
    assert compute_channel_metrics(db_session, datetime.utcnow() - timedelta(days=30)) == []
