import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Ticket, Customer, Investigation
from app.db.database import SessionLocal, Base, get_db
from app.main import app

client = TestClient(app)

@pytest.fixture
def db_session():
    db = SessionLocal()
    yield db
    db.close()

def test_inbox_list_all_tickets_with_customer_and_sorting(db_session):
    """
    Test that /api/inbox returns all tickets, sorted newest first,
    with real customer data and channel keys.
    """
    # Let's count existing tickets in the seeded db
    initial_count = db_session.query(Ticket).count()

    # Add a couple of new tickets with explicit timestamps
    c1 = Customer(name="Alice Inbox", email="alice.inbox@example.com")
    c2 = Customer(name="Bob Inbox", email="bob.inbox@example.com")
    db_session.add_all([c1, c2])
    db_session.commit()

    now = datetime.utcnow()
    t1 = Ticket(customer_id=c1.id, subject="First Subject", message="Short msg", channel_key="live_chat", status="open", created_at=now - timedelta(days=2))
    t2 = Ticket(customer_id=c2.id, subject="Second Subject", message="Long message " * 10, channel_key="email", status="resolved", created_at=now)
    db_session.add_all([t1, t2])
    db_session.commit()

    inv = Investigation(ticket_id=t1.id, customer_id=c1.id, status="investigating", started_at=now)
    db_session.add(inv)
    db_session.commit()

    response = client.get("/api/inbox")
    assert response.status_code == 200
    data = response.json()

    # Exactly one row per ticket
    assert len(data) == initial_count + 2

    # Sorting: newest first
    assert data[0]["id"] == t2.id
    # Test customer data
    assert data[0]["customer"]["name"] == "Bob Inbox"
    assert data[0]["channel_key"] == "email"
    assert data[0]["status"] == "resolved"
    assert data[0]["has_investigation"] is False
    assert len(data[0]["preview"]) > 50
    assert "..." in data[0]["preview"]

    # Find t1 in the list to check investigation
    t1_data = next(d for d in data if d["id"] == t1.id)
    assert t1_data["customer"]["name"] == "Alice Inbox"
    assert t1_data["has_investigation"] is True
    assert t1_data["channel_key"] == "live_chat"
    assert t1_data["preview"] == "Short msg"

def test_inbox_detail_success(db_session):
    """
    Test /api/inbox/{ticket_id} returns exact conversation details
    and links to investigation if present.
    """
    c = Customer(name="Detail Customer", email="detail@example.com")
    db_session.add(c)
    db_session.commit()

    t = Ticket(customer_id=c.id, subject="Detail Subject", message="Detail message here", channel_key="whatsapp", status="escalated")
    db_session.add(t)
    db_session.commit()

    inv = Investigation(ticket_id=t.id, customer_id=c.id, status="root_cause_found")
    db_session.add(inv)
    db_session.commit()

    response = client.get(f"/api/inbox/{t.id}")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == t.id
    assert data["customer"]["name"] == "Detail Customer"
    assert data["channel_key"] == "whatsapp"
    assert data["subject"] == "Detail Subject"
    assert data["message"] == "Detail message here"
    assert data["status"] == "escalated"
    assert data["investigation_id"] == inv.id

def test_inbox_detail_not_found(db_session):
    """
    Test /api/inbox/{ticket_id} failure edge case.
    """
    response = client.get("/api/inbox/9999999")
    assert response.status_code == 404

from sqlalchemy.pool import StaticPool

def test_empty_inbox():
    """
    Test empty inbox edge case using an isolated in-memory SQLite database
    so we don't pollute the shared test database.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/api/inbox")
        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.clear()

def test_inbox_channel_filtering():
    """
    Test channel filtering edge cases using isolated in-memory SQLite database.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        db = TestingSessionLocal()
        from app.db.models import Channel

        # Add a valid channel
        c = Channel(key="test_channel", display_name="Test Channel", status="active")
        db.add(c)
        db.commit()

        # Add some tickets
        cust = Customer(name="Test Cust", email="test@cust.com")
        db.add(cust)
        db.commit()

        now = datetime.utcnow()
        t1 = Ticket(customer_id=cust.id, subject="T1", message="M1", channel_key="test_channel", status="open", created_at=now - timedelta(days=1))
        t2 = Ticket(customer_id=cust.id, subject="T2", message="M2", channel_key="other_channel", status="open", created_at=now)
        db.add_all([t1, t2])
        db.commit()

        # Test 1: Invalid channel -> 400
        response = client.get("/api/inbox?channel=invalid_channel")
        assert response.status_code == 400
        assert "Invalid channel" in response.json()["detail"]

        # Test 2: Valid channel filtering (only 1 result)
        response = client.get("/api/inbox?channel=test_channel")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["subject"] == "T1"
        assert data[0]["channel_key"] == "test_channel"

        # Test 3: Zero conversations for valid channel
        c2 = Channel(key="empty_channel", display_name="Empty", status="active")
        db.add(c2)
        db.commit()

        response = client.get("/api/inbox?channel=empty_channel")
        assert response.status_code == 200
        assert response.json() == []

        # Test 4: Ordering preserved and exactly one row per ticket
        t3 = Ticket(customer_id=cust.id, subject="T3", message="M3", channel_key="test_channel", status="open", created_at=now + timedelta(days=1))
        db.add(t3)
        db.commit()

        response = client.get("/api/inbox?channel=test_channel")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # newest first
        assert data[0]["subject"] == "T3"
        assert data[1]["subject"] == "T1"

    finally:
        app.dependency_overrides.clear()
        db.close()

