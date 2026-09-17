import pytest
from app.db.database import SessionLocal
from app.db.models import Customer, Order
from app.tools.mock_tools import check_payment_issue, issue_refund


@pytest.fixture
def db_session():
    with SessionLocal() as db:
        yield db
        db.close()


def test_payment_detection_duplicate(db_session):
    customer = Customer(name="Test Dup", email="dup@example.com")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    # Original
    o1 = Order(customer_id=customer.id, product="Item", amount=10.0, status="processing", payment_status="paid")
    db_session.add(o1)
    db_session.commit()
    db_session.refresh(o1)

    # Duplicate
    o2 = Order(customer_id=customer.id, product="Item", amount=10.0, status="processing", payment_status="paid", duplicate_of=o1.id)
    db_session.add(o2)
    db_session.commit()
    db_session.refresh(o2)

    res = check_payment_issue(db_session, o2.id)
    assert res["detected"] is True
    assert res["issue_type"] == "duplicate_payment"
    assert res["related_order_id"] == o1.id
    
    # Original should not be flagged as a duplicate
    res_orig = check_payment_issue(db_session, o1.id)
    assert res_orig["detected"] is False


def test_payment_detection_mismatch(db_session):
    customer = Customer(name="Test Mis", email="mis@example.com")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    # Mismatch
    o1 = Order(customer_id=customer.id, product="Item", amount=10.0, status="failed", payment_status="paid")
    db_session.add(o1)
    db_session.commit()
    db_session.refresh(o1)

    res = check_payment_issue(db_session, o1.id)
    assert res["detected"] is True
    assert res["issue_type"] == "payment_fulfillment_mismatch"
    assert res["fulfillment_status"] == "failed"
    assert res["payment_status"] == "paid"


def test_refund_idempotency(db_session):
    customer = Customer(name="Test Ref", email="ref@example.com")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    o1 = Order(customer_id=customer.id, product="Item", amount=10.0, status="processing", payment_status="paid")
    db_session.add(o1)
    db_session.commit()
    db_session.refresh(o1)

    res1 = issue_refund(db_session, o1.id)
    assert res1["success"] is True
    assert res1["payment_status"] == "refunded"
    assert res1["status"] == "refunded"

    # Second refund should fail gracefully
    res2 = issue_refund(db_session, o1.id)
    assert res2["success"] is False
    assert res2["error"] == "Order already refunded"

    # Check payment issue should identify it's already refunded
    res_check = check_payment_issue(db_session, o1.id)
    assert res_check["detected"] is False
    assert res_check["error"] == "Already refunded"
