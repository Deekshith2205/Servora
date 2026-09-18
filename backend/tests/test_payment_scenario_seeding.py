"""Connected Commerce demo polish: seed_payment_scenarios_if_missing()'s
own idempotency guard — this needs its OWN check distinct from
`seed_if_empty()`'s "any customer exists" guard, since the real deployed
Neon database already had Alice/Bob seeded long before the Payment table
existed (see that function's own docstring for why). Same
fresh-isolated-engine pattern test_demo_data_channels.py already
established, for the same class of reason (a shared test DB other files
mutate would make "does this data exist" fragile/order-dependent).
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.db.seed as seed_module
from app.db.database import Base
from app.db.models import Customer, Payment, Ticket


@pytest.fixture
def fresh_seeded_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    fresh_session_local = sessionmaker(bind=engine)
    monkeypatch.setattr(seed_module, "SessionLocal", fresh_session_local)

    seed_module.seed_if_empty()

    session = fresh_session_local()
    try:
        yield session
    finally:
        session.close()


def test_fresh_seed_creates_all_six_payment_scenarios_for_alice(fresh_seeded_session):
    alice = fresh_seeded_session.query(Customer).filter(Customer.email == "alice@example.com").first()
    payments = fresh_seeded_session.query(Payment).filter(Payment.customer_id == alice.id).all()

    issue_types_present = set()
    if any(p.duplicate_of is not None and p.order_id is None for p in payments):
        issue_types_present.add("duplicate_payment_no_order")
    if any(p.status == "refund_pending" for p in payments):
        issue_types_present.add("refund_delayed")
    if any(p.payment_type == "subscription" for p in payments):
        issue_types_present.add("subscription")

    assert issue_types_present == {"duplicate_payment_no_order", "refund_delayed", "subscription"}
    # 2 earbuds payments (original + duplicate) + 1 lamp + 1 air fryer +
    # 1 subscription = 5 (the wrong-item and damaged-package scenarios
    # are Order/Ticket-only, no Payment row — see seed.py).
    assert len(payments) == 5


def test_fresh_seed_creates_matching_tickets_for_the_new_scenarios(fresh_seeded_session):
    alice = fresh_seeded_session.query(Customer).filter(Customer.email == "alice@example.com").first()
    subjects = {
        t.subject for t in fresh_seeded_session.query(Ticket).filter(Ticket.customer_id == alice.id).all()
    }
    assert "Charged twice for earbuds" in subjects
    assert "Refund still not received" in subjects
    assert "Received the wrong item" in subjects
    assert "Cancelled order, no refund" in subjects
    assert "Package arrived damaged" in subjects
    assert "Charged after cancelling subscription" in subjects


def test_running_seed_if_empty_twice_does_not_duplicate_payment_rows(fresh_seeded_session):
    before = fresh_seeded_session.query(Payment).count()
    seed_module.seed_if_empty()
    after = fresh_seeded_session.query(Payment).count()
    assert before == after


def test_seed_payment_scenarios_backfills_an_already_seeded_database(monkeypatch):
    """The real-world case this function exists for: a database that
    already had Alice/Bob (and no Payment table's worth of data) before
    this feature existed — seed_if_empty() returns early on
    `db.query(Customer).first()`, but the payment-scenario backfill must
    still run."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    fresh_session_local = sessionmaker(bind=engine)
    monkeypatch.setattr(seed_module, "SessionLocal", fresh_session_local)

    # Simulate a pre-existing database: only Alice/Bob exist, seeded
    # WITHOUT any Payment rows (as if seed_if_empty() ran before the
    # Payment table existed).
    session = fresh_session_local()
    alice = Customer(name="Alice Rao", email="alice@example.com")
    session.add(alice)
    session.commit()
    alice_id = alice.id
    session.close()

    seed_module.seed_if_empty()

    session = fresh_session_local()
    try:
        payments = session.query(Payment).filter(Payment.customer_id == alice_id).all()
        assert len(payments) == 5
    finally:
        session.close()
