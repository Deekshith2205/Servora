import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from sqlalchemy.pool import StaticPool

from app.db.models import Ticket, Customer, Investigation, Channel
from app.db.database import SessionLocal, Base, get_db
from app.main import app

client = TestClient(app)

@pytest.fixture
def db_session():
    with SessionLocal() as db:
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

def test_dashboard_channel_counts_consistency_with_inbox(db_session):
    """
    [Omnichannel] issue #154 requires a focused verification that Dashboard 
    channel counts (calculated client-side from the open inbox items) 
    match the Inbox channel-filtered API counts.
    """
    # Create test data
    c = Customer(name="Dashboard Test", email="dashboard@example.com")
    db_session.add(c)
    db_session.commit()
    
    # 2 open whatsapp, 1 resolved whatsapp, 1 open email
    db_session.add_all([
        Ticket(customer_id=c.id, subject="s1", message="m", channel_key="whatsapp", status="open"),
        Ticket(customer_id=c.id, subject="s2", message="m", channel_key="whatsapp", status="open"),
        Ticket(customer_id=c.id, subject="s3", message="m", channel_key="whatsapp", status="resolved"),
        Ticket(customer_id=c.id, subject="s4", message="m", channel_key="email", status="open"),
    ])
    db_session.commit()

    # What the dashboard fetches:
    all_open_resp = client.get("/api/inbox?status=open")
    assert all_open_resp.status_code == 200
    all_open_items = all_open_resp.json()

    # Dashboard client-side calculation for whatsapp:
    dashboard_whatsapp_open = len([t for t in all_open_items if t["channel_key"] == "whatsapp"])
    
    # What the Inbox fetch uses for the channel tab:
    channel_open_resp = client.get("/api/inbox?channel=whatsapp&status=open")
    assert channel_open_resp.status_code == 200
    channel_open_items = channel_open_resp.json()
    
    # Verify consistency
    assert dashboard_whatsapp_open == len(channel_open_items)
    
    # Sanity check against actual test data (should be 2)
    assert dashboard_whatsapp_open >= 2

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


def _setup_isolated_db_for_search():
    engine = create_engine(
        "sqlite://", 
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    
    channels = [
        Channel(key="whatsapp", display_name="WhatsApp", status="active"),
        Channel(key="email", display_name="Email", status="active"),
    ]
    db.add_all(channels)
    
    c1 = Customer(name="Alice Smith", email="alice@example.com")
    c2 = Customer(name="Bob Jones", email="bob@test.com")
    db.add_all([c1, c2])
    db.commit()
    
    now = datetime.utcnow()
    t1 = Ticket(customer_id=c1.id, subject="T1", message="Help me with login", channel_key="whatsapp", status="open", created_at=now - timedelta(days=2))
    t2 = Ticket(customer_id=c2.id, subject="T2", message="Billing issue ALICE related", channel_key="email", status="resolved", created_at=now - timedelta(days=1))
    t3 = Ticket(customer_id=c1.id, subject="T3", message="Another question", channel_key="email", status="escalated", created_at=now)
    db.add_all([t1, t2, t3])
    db.commit()
    db.close()
    
    def override_get_db():
        try:
            session = TestingSessionLocal()
            yield session
        finally:
            session.close()
            
    return override_get_db


def test_inbox_search_and_filter():
    app.dependency_overrides[get_db] = _setup_isolated_db_for_search()
    try:
        # no filters equals current unfiltered behavior
        r = client.get("/api/inbox")
        assert r.status_code == 200
        assert len(r.json()) == 3
        # newest first
        assert r.json()[0]["subject"] == "T3"

        # whitespace-only q
        r = client.get("/api/inbox?q=   ")
        assert len(r.json()) == 3

        # customer-name search
        r = client.get("/api/inbox?q=Alice")
        assert len(r.json()) == 3 # T1 and T3 match name, T2 matches message text "ALICE"

        r = client.get("/api/inbox?q=bob") # case-insensitive
        assert len(r.json()) == 1
        assert r.json()[0]["subject"] == "T2"

        # customer-email search
        r = client.get("/api/inbox?q=test.com")
        assert len(r.json()) == 1

        # message-text search
        r = client.get("/api/inbox?q=login")
        assert len(r.json()) == 1
        assert r.json()[0]["subject"] == "T1"

        # no-match
        r = client.get("/api/inbox?q=xyzzzzz")
        assert len(r.json()) == 0

        # each supported status
        r = client.get("/api/inbox?status=open")
        assert len(r.json()) == 1
        r = client.get("/api/inbox?status=resolved")
        assert len(r.json()) == 1
        r = client.get("/api/inbox?status=escalated")
        assert len(r.json()) == 1

        # invalid status behavior
        r = client.get("/api/inbox?status=invalid")
        assert r.status_code == 400

        # channel + q
        r = client.get("/api/inbox?channel=whatsapp&q=alice")
        assert len(r.json()) == 1 # Only T1

        # channel + status
        r = client.get("/api/inbox?channel=email&status=resolved")
        assert len(r.json()) == 1 # T2

        # q + status
        r = client.get("/api/inbox?q=alice&status=escalated")
        assert len(r.json()) == 1 # T3

        # channel + q + status
        r = client.get("/api/inbox?channel=email&q=alice&status=resolved")
        assert len(r.json()) == 1 # T2 (matches q="alice" via message, channel=email, status=resolved)

        # one-row-per-ticket remains true
        inv = Investigation(ticket_id=1, customer_id=1, status="investigating")
        db = next(_setup_isolated_db_for_search()())
        db.add(inv)
        db.commit()
        db.close()
        r = client.get("/api/inbox")
        assert len(r.json()) == 3

    finally:
        app.dependency_overrides.clear()
