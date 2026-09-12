"""Tests for issue #17's API surface: POST /api/escalations/{id}/resolve
and POST/GET /api/kb-articles.

Uses the real app + real DB via TestClient (`with TestClient(app) as
client:` — required so the lifespan actually runs, see conftest.py's own
note on this). Only the Learning Agent's LLM call is mocked.
"""
from app.agents.learning import DraftKBArticle
from app.db.database import SessionLocal
from app.db.models import KBArticle, Ticket
from app.main import app
from fastapi.testclient import TestClient


def test_resolve_marks_ticket_resolved_and_returns_no_suggestion(monkeypatch):
    db = SessionLocal()
    db.query(Ticket).delete()
    db.commit()
    ticket = Ticket(customer_id=1, category="billing", subject="fee waiver", message="waive my fee", status="open")
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    monkeypatch.setattr(
        "app.api.tickets.draft_kb_article",
        lambda **kwargs: DraftKBArticle(should_add=False, title="", body="", tags=[]),
    )

    with TestClient(app) as client:
        resp = client.post(f"/api/escalations/{ticket.id}/resolve", json={"resolution_notes": "one-time waiver"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["ticket"]["status"] == "resolved"
    assert body["kb_suggestion"]["should_add"] is False


def test_resolve_returns_a_real_suggestion_when_reusable(monkeypatch):
    db = SessionLocal()
    db.query(Ticket).delete()
    db.commit()
    ticket = Ticket(customer_id=1, category="billing", subject="dup charge", message="charged twice", status="escalated")
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    monkeypatch.setattr(
        "app.api.tickets.draft_kb_article",
        lambda **kwargs: DraftKBArticle(
            should_add=True, title="Legacy plan refund process", body="Migrate then refund.", tags=["billing"]
        ),
    )

    with TestClient(app) as client:
        resp = client.post(f"/api/escalations/{ticket.id}/resolve", json={"resolution_notes": "migrated then refunded"})

    body = resp.json()
    assert body["kb_suggestion"]["should_add"] is True
    assert body["kb_suggestion"]["title"] == "Legacy plan refund process"


def test_resolve_404_for_missing_ticket():
    with TestClient(app) as client:
        resp = client.post("/api/escalations/999999/resolve", json={"resolution_notes": "x"})
    assert resp.status_code == 404


def test_resolve_survives_llm_failure(monkeypatch):
    """Best-effort, like orchestrator.py's _update_memory(): a failed draft
    must never block marking the ticket resolved."""
    from app.llm import LLMError

    db = SessionLocal()
    db.query(Ticket).delete()
    db.commit()
    ticket = Ticket(customer_id=1, category="order", subject="x", message="x", status="open")
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    def _raise(**kwargs):
        raise LLMError("no key configured")

    monkeypatch.setattr("app.api.tickets.draft_kb_article", _raise)

    with TestClient(app) as client:
        resp = client.post(f"/api/escalations/{ticket.id}/resolve", json={"resolution_notes": "x"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["ticket"]["status"] == "resolved"
    assert body["kb_suggestion"] is None


def test_approve_kb_article_inserts_a_real_row():
    db = SessionLocal()
    db.query(KBArticle).delete()
    db.commit()

    with TestClient(app) as client:
        resp = client.post(
            "/api/kb-articles",
            json={"title": "Test article", "body": "Test body", "tags": ["billing", "refund"]},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Test article"
    assert body["tags"] == "billing,refund"

    saved = SessionLocal().get(KBArticle, body["id"])
    assert saved is not None
    assert saved.title == "Test article"


def test_list_kb_articles_returns_inserted_articles():
    db = SessionLocal()
    db.query(KBArticle).delete()
    db.commit()
    db.add(KBArticle(title="Existing", body="Body", tags="order"))
    db.commit()

    with TestClient(app) as client:
        resp = client.get("/api/kb-articles")

    assert resp.status_code == 200
    titles = [a["title"] for a in resp.json()]
    assert "Existing" in titles
