"""Connected Commerce demo-polish pass: the 3 new payment-only anomaly
types (see app/db/models.py::Payment and app/tools/mock_tools.py::
check_payment_anomaly) that `check_payment_issue`/`issue_refund` can't
represent because they always assume a linked Order. Mirrors
test_billing.py's own fixture/assertion style for the existing
order-based anomalies.
"""
import uuid
from datetime import datetime, timedelta

import pytest
from app.db.database import SessionLocal
from app.db.models import Customer, Payment
from app.tools.mock_tools import REFUND_DELAY_THRESHOLD_DAYS, check_payment_anomaly, get_customer_payments, issue_payment_refund


@pytest.fixture
def db_session():
    with SessionLocal() as db:
        yield db
        db.close()


@pytest.fixture
def customer(db_session):
    # A unique email per test — this fixture's rows persist in the
    # shared, file-based test DB across the whole test session (same
    # convention test_billing.py's own per-test unique emails follow),
    # so a fixed email would collide with a UNIQUE constraint the
    # second time any test using this fixture runs.
    c = Customer(name="Test Payments", email=f"test-payments-{uuid.uuid4().hex[:8]}@example.com")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


def test_get_customer_payments_returns_only_this_customers_rows(db_session, customer):
    other = Customer(name="Someone Else", email=f"someone-else-{uuid.uuid4().hex[:8]}@example.com")
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    db_session.add_all([
        Payment(customer_id=customer.id, amount=10.0, status="paid"),
        Payment(customer_id=other.id, amount=20.0, status="paid"),
    ])
    db_session.commit()

    results = get_customer_payments(db_session, customer.id)
    assert len(results) == 1
    assert results[0].customer_id == customer.id


def test_duplicate_payment_with_no_order_is_detected(db_session, customer):
    original = Payment(customer_id=customer.id, order_id=None, amount=50.0, status="paid")
    db_session.add(original)
    db_session.commit()
    db_session.refresh(original)

    duplicate = Payment(customer_id=customer.id, order_id=None, amount=50.0, status="paid", duplicate_of=original.id)
    db_session.add(duplicate)
    db_session.commit()
    db_session.refresh(duplicate)

    res = check_payment_anomaly(db_session, duplicate.id)
    assert res["detected"] is True
    assert res["issue_type"] == "duplicate_payment_no_order"
    assert res["related_payment_id"] == original.id

    # The original itself is not flagged — it has no duplicate_of set.
    res_orig = check_payment_anomaly(db_session, original.id)
    assert res_orig["detected"] is False


def test_subscription_charged_after_cancellation_is_detected(db_session, customer):
    now = datetime.utcnow()
    payment = Payment(
        customer_id=customer.id, order_id=None, amount=14.99, status="paid",
        payment_type="subscription",
        subscription_cancelled_at=now - timedelta(days=5),
        charged_at=now - timedelta(days=2),  # charged AFTER cancellation
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)

    res = check_payment_anomaly(db_session, payment.id)
    assert res["detected"] is True
    assert res["issue_type"] == "subscription_charged_after_cancellation"


def test_subscription_charged_before_cancellation_is_not_flagged(db_session, customer):
    now = datetime.utcnow()
    payment = Payment(
        customer_id=customer.id, order_id=None, amount=14.99, status="paid",
        payment_type="subscription",
        charged_at=now - timedelta(days=30),
        subscription_cancelled_at=now - timedelta(days=5),  # cancelled AFTER this charge
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)

    res = check_payment_anomaly(db_session, payment.id)
    assert res["detected"] is False


def test_refund_delay_past_threshold_is_detected(db_session, customer):
    now = datetime.utcnow()
    payment = Payment(
        customer_id=customer.id, amount=30.0, status="refund_pending",
        refund_requested_at=now - timedelta(days=REFUND_DELAY_THRESHOLD_DAYS + 1),
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)

    res = check_payment_anomaly(db_session, payment.id)
    assert res["detected"] is True
    assert res["issue_type"] == "refund_delayed"


def test_refund_delay_within_threshold_is_not_flagged(db_session, customer):
    now = datetime.utcnow()
    payment = Payment(
        customer_id=customer.id, amount=30.0, status="refund_pending",
        refund_requested_at=now - timedelta(days=1),
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)

    res = check_payment_anomaly(db_session, payment.id)
    assert res["detected"] is False


def test_issue_payment_refund_idempotency(db_session, customer):
    payment = Payment(customer_id=customer.id, amount=25.0, status="refund_pending")
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)

    res1 = issue_payment_refund(db_session, payment.id)
    assert res1["success"] is True
    assert res1["status"] == "refunded"

    res2 = issue_payment_refund(db_session, payment.id)
    assert res2["success"] is False
    assert res2["error"] == "Payment already refunded"

    res_check = check_payment_anomaly(db_session, payment.id)
    assert res_check["detected"] is False
    assert res_check["error"] == "Already refunded"


def test_check_payment_anomaly_unknown_payment(db_session):
    res = check_payment_anomaly(db_session, 999999)
    assert res["detected"] is False
    assert res["error"] == "Payment not found"
