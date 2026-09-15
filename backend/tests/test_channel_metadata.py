"""[Omnichannel] issue #134 — message source metadata.

Proves the issue's acceptance criteria: a channel-metadata-bearing
investigation (simulating a WhatsApp origin) persists a real, non-empty
`channel_metadata_json`; a Live Chat investigation (the common,
unchanged case) has `channel_metadata_json = None`, never a fabricated
empty object; and `GET /api/investigations/{id}` exposes
`channel_metadata` in its response.
"""
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.orchestrator as orchestrator_module
from app.agents.classifier import ClassificationResult
from app.agents.critic import CriticReview
from app.agents.planner import PlanDecision
from app.agents.specialists import SpecialistResponse
from app.agents.verification import VerificationResult
from app.db.database import Base
from app.db.models import Customer, Investigation
from app.main import app
from app.orchestrator import handle_message

_MOCK_CRITIC_REVIEW = CriticReview(agrees=True, confidence=0.8, alternative_hypothesis=None, reasoning="mocked for test")

client = TestClient(app)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _mock_resolved_path(monkeypatch):
    monkeypatch.setattr(
        orchestrator_module, "classify",
        lambda message: ClassificationResult(category="order", sentiment="neutral", urgency=3, reasoning="r", confidence=0.9),
    )
    monkeypatch.setattr(
        orchestrator_module, "plan",
        lambda classification, customer_id, db: PlanDecision(action="resolve", target_agent="technical", reasoning="r"),
    )
    monkeypatch.setattr(
        orchestrator_module, "SPECIALISTS",
        {"technical": lambda db, customer_id, message: SpecialistResponse(reply="fixed it", used_tools=[], confidence=0.6)},
    )
    monkeypatch.setattr(orchestrator_module, "critique", lambda response, message: _MOCK_CRITIC_REVIEW)
    monkeypatch.setattr(orchestrator_module, "verify", lambda response: VerificationResult(approved=True, reasoning="ok"))
    monkeypatch.setattr(orchestrator_module, "extract_facts", lambda message, reply: [])


def test_channel_metadata_property_parses_json():
    inv = Investigation(ticket_id=1, customer_id=1, channel_metadata_json='{"external_conversation_id": "wamid.abc"}')
    assert inv.channel_metadata == {"external_conversation_id": "wamid.abc"}


def test_channel_metadata_property_is_none_when_unset():
    inv = Investigation(ticket_id=1, customer_id=1)
    assert inv.channel_metadata is None


def test_handle_message_with_no_channel_metadata_leaves_it_none(monkeypatch, db_session):
    customer = Customer(name="Alice", email="alice-cm-default@example.com", tier="vip")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    _mock_resolved_path(monkeypatch)

    result = handle_message(db_session, customer.id, "something")

    investigation = db_session.query(Investigation).filter(Investigation.ticket_id == result.ticket_id).first()
    assert investigation.channel_metadata_json is None
    assert investigation.channel_metadata is None


def test_handle_message_persists_real_channel_metadata(monkeypatch, db_session):
    customer = Customer(name="Bob", email="bob-cm-whatsapp@example.com", tier="standard")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    _mock_resolved_path(monkeypatch)

    metadata = {"external_conversation_id": "wamid.HBgLMTU1NTU1NTU1NTUVAgARGA", "external_contact": "+15555550101"}
    result = handle_message(db_session, customer.id, "something", channel="whatsapp", channel_metadata=metadata)

    investigation = db_session.query(Investigation).filter(Investigation.ticket_id == result.ticket_id).first()
    assert investigation.channel_metadata == metadata


def test_get_investigation_exposes_channel_metadata(monkeypatch):
    monkeypatch.setattr(
        "app.orchestrator.classify",
        lambda message: ClassificationResult(category="order", sentiment="neutral", urgency=3, reasoning="mocked", confidence=0.9),
    )
    monkeypatch.setattr(
        "app.orchestrator.plan",
        lambda classification, customer_id, db: PlanDecision(action="resolve", target_agent="order", reasoning="mocked"),
    )
    mocked_specialist = lambda db, customer_id, message: SpecialistResponse(reply="mocked reply", used_tools=[], confidence=0.9)
    monkeypatch.setattr("app.orchestrator.SPECIALISTS", {"order": mocked_specialist, "technical": mocked_specialist})
    monkeypatch.setattr("app.orchestrator.critique", lambda response, message: _MOCK_CRITIC_REVIEW)
    monkeypatch.setattr("app.orchestrator.extract_facts", lambda message, reply: [])

    # Live Chat (default): channel_metadata stays None end-to-end.
    resp = client.post("/api/chat", json={"customer_id": 1, "message": "Where is my order?"})
    assert resp.status_code == 200
    ticket_id = resp.json()["ticket_id"]

    inv_resp = client.get(f"/api/investigations/by-ticket/{ticket_id}")
    assert inv_resp.status_code == 200
    assert inv_resp.json()["channel_metadata"] is None
