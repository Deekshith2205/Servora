import pytest
from sqlalchemy.orm import Session
from typing import Callable
from dataclasses import dataclass

from app.db.models import Order, Customer, Ticket
from app.tools.mock_tools import check_order_issue
from app.agents.specialists import _run_specialist, _ORDER_SYSTEM_PROMPT
from app.db.database import SessionLocal


@pytest.fixture
def db_session():
    with SessionLocal() as db:
        yield db
        db.close()


def test_check_order_issue_cancelled(db_session):
    customer = Customer(name="Test", email="test@test.com")
    db_session.add(customer)
    db_session.commit()
    
    order = Order(customer_id=customer.id, product="Tablet", amount=399.00, status="cancelled", payment_status="refunded")
    db_session.add(order)
    db_session.commit()
    
    result = check_order_issue(db_session, order.id)
    assert result["detected"] is True
    assert result["issue_type"] == "cancelled_order"
    assert result["status"] == "cancelled"


def test_check_order_issue_inventory(db_session):
    customer = Customer(name="Test", email="test2@test.com")
    db_session.add(customer)
    db_session.commit()
    
    order = Order(
        customer_id=customer.id, 
        product="Keyboard", 
        amount=149.99, 
        status="failed", 
        payment_status="paid", 
        failure_reason="inventory_shortfall"
    )
    db_session.add(order)
    db_session.commit()
    
    result = check_order_issue(db_session, order.id)
    assert result["detected"] is True
    assert result["issue_type"] == "inventory_shortfall"
    assert result["status"] == "failed"
    assert result["failure_reason"] == "inventory_shortfall"


def test_check_order_issue_normal_failed(db_session):
    customer = Customer(name="Test", email="test3@test.com")
    db_session.add(customer)
    db_session.commit()
    
    # Failed but not inventory shortfall
    order = Order(
        customer_id=customer.id, 
        product="Keyboard", 
        amount=149.99, 
        status="failed", 
        payment_status="paid", 
        failure_reason="payment_declined"
    )
    db_session.add(order)
    db_session.commit()
    
    result = check_order_issue(db_session, order.id)
    assert result["detected"] is False


def test_check_order_issue_normal(db_session):
    customer = Customer(name="Test", email="test4@test.com")
    db_session.add(customer)
    db_session.commit()
    
    order = Order(customer_id=customer.id, product="Keyboard", amount=149.99, status="processing")
    db_session.add(order)
    db_session.commit()
    
    result = check_order_issue(db_session, order.id)
    assert result["detected"] is False


def test_check_order_issue_missing(db_session):
    result = check_order_issue(db_session, 99999)
    assert result["detected"] is False
    assert result["error"] == "Order not found"


def test_order_specialist_cancelled(db_session, monkeypatch):
    customer = Customer(name="Test", email="test5@test.com")
    db_session.add(customer)
    db_session.commit()
    
    order = Order(customer_id=customer.id, product="Tablet", amount=399.00, status="cancelled", payment_status="refunded")
    db_session.add(order)
    db_session.commit()

    def mock_call_llm(*args, **kwargs):
        # We need to simulate the LLM calling check_order_issue
        tools_tuple = kwargs.get("tools")
        if tools_tuple:
            _, handlers = tools_tuple
            handlers["check_order_issue"]({"order_id": order.id})
            kwargs["tool_call_log"].append("check_order_issue")
        return "Your order is cancelled."

    monkeypatch.setattr("app.agents.specialists.call_llm", mock_call_llm)

    response = _run_specialist(db_session, _ORDER_SYSTEM_PROMPT, customer.id, "Where is my tablet?", specialist="order")
    assert "Your order is cancelled" in response.reply
    assert "check_order_issue" in response.used_tools
    assert response.root_cause == "Order was cancelled."
    assert response.resolution == "The order is cancelled and requires no further fulfillment processing."
    assert response.confidence == 0.6


def test_order_specialist_inventory(db_session, monkeypatch):
    customer = Customer(name="Test", email="test6@test.com")
    db_session.add(customer)
    db_session.commit()
    
    order = Order(
        customer_id=customer.id, 
        product="Keyboard", 
        amount=149.99, 
        status="failed", 
        payment_status="paid", 
        failure_reason="inventory_shortfall"
    )
    db_session.add(order)
    db_session.commit()

    def mock_call_llm(*args, **kwargs):
        tools_tuple = kwargs.get("tools")
        if tools_tuple:
            _, handlers = tools_tuple
            handlers["check_order_issue"]({"order_id": order.id})
            kwargs["tool_call_log"].append("check_order_issue")
        return "Fulfillment failed due to inventory."

    monkeypatch.setattr("app.agents.specialists.call_llm", mock_call_llm)

    response = _run_specialist(db_session, _ORDER_SYSTEM_PROMPT, customer.id, "Where is my keyboard?", specialist="order")
    assert "Fulfillment failed" in response.reply
    assert "check_order_issue" in response.used_tools
    assert response.root_cause == "Order fulfillment failed because inventory was unavailable."
    assert response.resolution == "The order requires a fulfillment remedy or human review."
    assert response.confidence == 0.6
