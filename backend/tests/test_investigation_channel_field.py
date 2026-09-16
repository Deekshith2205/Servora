"""[Omnichannel] issue #146 — Channel information in investigations.

`Investigation.channel_key` has existed since issue #133, but
`InvestigationOut`/`InvestigationListItemOut` never actually exposed it
through the read API — this proves both now do, for old and new rows
alike, over real HTTP.

[RBAC]: `GET /api/investigations` (list) requires `view_investigation_board`
and `GET /api/investigations/by-ticket/{id}` requires either that same
permission or (for a Customer) ownership of the investigation — every
call below sends a real Administrator identity header, which satisfies
both.
"""
from fastapi.testclient import TestClient

from app.agents.classifier import ClassificationResult
from app.agents.critic import CriticReview
from app.agents.planner import PlanDecision
from app.agents.specialists import SpecialistResponse
from app.db.database import SessionLocal
from app.main import app
from tests.rbac_headers import staff_headers

_MOCK_CRITIC_REVIEW = CriticReview(agrees=True, confidence=0.8, alternative_hypothesis=None, reasoning="mocked for test")

client = TestClient(app)


def _mock_resolved_path(monkeypatch):
    monkeypatch.setattr(
        "app.orchestrator.classify",
        lambda message: ClassificationResult(category="order", sentiment="neutral", urgency=3, reasoning="mocked", confidence=0.9),
    )
    monkeypatch.setattr(
        "app.orchestrator.plan",
        lambda classification, customer_id, db: PlanDecision(action="resolve", target_agent="order", reasoning="mocked"),
    )
    mocked_specialist = lambda db, customer_id, message, channel="live_chat": SpecialistResponse(reply="mocked reply", used_tools=[], confidence=0.9)
    monkeypatch.setattr("app.orchestrator.SPECIALISTS", {"order": mocked_specialist, "technical": mocked_specialist})
    monkeypatch.setattr("app.orchestrator.critique", lambda response, message: _MOCK_CRITIC_REVIEW)
    monkeypatch.setattr("app.orchestrator.extract_facts", lambda message, reply: [])


def _admin_headers():
    db = SessionLocal()
    headers = staff_headers(db, "administrator")
    db.close()
    return headers


def test_get_investigation_by_ticket_exposes_real_channel(monkeypatch):
    _mock_resolved_path(monkeypatch)
    headers = _admin_headers()

    resp = client.post("/api/chat", json={"customer_id": 1, "message": "Where is my order?", "channel": "whatsapp"})
    assert resp.status_code == 200
    ticket_id = resp.json()["ticket_id"]

    inv_resp = client.get(f"/api/investigations/by-ticket/{ticket_id}", headers=headers)
    assert inv_resp.status_code == 200
    assert inv_resp.json()["channel"] == "whatsapp"


def test_get_investigation_by_ticket_defaults_channel_to_live_chat(monkeypatch):
    _mock_resolved_path(monkeypatch)
    headers = _admin_headers()

    resp = client.post("/api/chat", json={"customer_id": 1, "message": "Where is my order?"})
    ticket_id = resp.json()["ticket_id"]

    inv_resp = client.get(f"/api/investigations/by-ticket/{ticket_id}", headers=headers)
    assert inv_resp.json()["channel"] == "live_chat"


def test_list_investigations_includes_real_channel_per_row(monkeypatch):
    _mock_resolved_path(monkeypatch)
    headers = _admin_headers()

    resp = client.post("/api/chat", json={"customer_id": 1, "message": "Where is my order?", "channel": "email"})
    ticket_id = resp.json()["ticket_id"]

    list_resp = client.get("/api/investigations?limit=50", headers=headers)
    assert list_resp.status_code == 200
    rows = list_resp.json()
    matching = [r for r in rows if r["ticket_id"] == ticket_id]
    assert len(matching) == 1
    assert matching[0]["channel"] == "email"
    # Every row has a real, non-null channel — old rows (created before
    # issue #133) read "live_chat", never a missing/null value.
    assert all(r["channel"] for r in rows)


def test_investigation_out_and_list_item_out_agree_on_channel(monkeypatch):
    """The same investigation's channel must read identically whether
    fetched via the full detail endpoint or the summary list — proves
    both builder sites (`_to_investigation_out()` and
    `list_investigations()`) were updated consistently, not just one."""
    _mock_resolved_path(monkeypatch)
    headers = _admin_headers()

    resp = client.post("/api/chat", json={"customer_id": 1, "message": "Where is my order?", "channel": "instagram"})
    ticket_id = resp.json()["ticket_id"]

    detail = client.get(f"/api/investigations/by-ticket/{ticket_id}", headers=headers).json()
    listed = next(r for r in client.get("/api/investigations?limit=50", headers=headers).json() if r["ticket_id"] == ticket_id)

    assert detail["channel"] == listed["channel"] == "instagram"
