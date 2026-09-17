"""Tests for app/rate_limit.py — the per-IP limiter on /api/chat and
/api/booking. Each one triggers a real LLM call chain (see that module's
own docstring for why this exists at all: hit live while testing the
Neon/Anthropic setup, a burst of manual requests alone was enough to
trip a free-tier provider key's own rate limit).

conftest.py disables this globally (RATE_LIMIT_ENABLED=false) so every
OTHER test file's fast, LLM-mocked requests never trip it — these tests
explicitly re-enable it for their own duration via monkeypatching
app.rate_limit.settings directly (patching the imported module-level
name, not app.config.settings, since rate_limit.py already bound its
own reference to the Settings instance at import time).
"""
from fastapi.testclient import TestClient

from app.agents.classifier import ClassificationResult
from app.agents.critic import CriticReview
from app.agents.planner import PlanDecision
from app.agents.specialists import SpecialistResponse
from app.db.database import SessionLocal
from app.db.models import Customer
from app.main import app
from app.rate_limit import _hits, rate_limit

_MOCK_CRITIC_REVIEW = CriticReview(agrees=True, confidence=0.8, alternative_hypothesis=None, reasoning="mocked for test")

client = TestClient(app)


def _reset_hits():
    _hits.clear()


def _seed_customer():
    with SessionLocal() as db:
        customer = Customer(name="Rate Limit Test Customer", email=f"rate-limit-{id(object())}@example.com")
        db.add(customer)
        db.commit()
        db.refresh(customer)
        return customer.id


def _mock_resolved_chat(monkeypatch):
    monkeypatch.setattr(
        "app.orchestrator.classify",
        lambda message: ClassificationResult(category="order", sentiment="neutral", urgency=3, reasoning="r", confidence=0.9),
    )
    monkeypatch.setattr(
        "app.orchestrator.plan",
        lambda classification, customer_id, db: PlanDecision(action="resolve", target_agent="technical", reasoning="r"),
    )
    monkeypatch.setattr(
        "app.orchestrator.SPECIALISTS",
        {"technical": lambda db, customer_id, message, channel="live_chat": SpecialistResponse(reply="ok", used_tools=[], confidence=0.6)},
    )
    monkeypatch.setattr("app.orchestrator.critique", lambda response, message: _MOCK_CRITIC_REVIEW)
    monkeypatch.setattr("app.orchestrator.extract_facts", lambda message, reply: [])


# --------------------------------------------------------------------- #
# Unit tests: the limiter function itself, no HTTP involved.
# --------------------------------------------------------------------- #


def test_allows_requests_under_the_limit():
    _reset_hits()
    from unittest.mock import MagicMock
    import app.rate_limit as rl

    fake_request = MagicMock()
    fake_request.client.host = "1.2.3.4"

    original_enabled, original_limit = rl.settings.rate_limit_enabled, rl.settings.rate_limit_requests
    rl.settings.rate_limit_enabled = True
    rl.settings.rate_limit_requests = 3
    try:
        for _ in range(3):
            rate_limit(fake_request)  # must not raise
    finally:
        rl.settings.rate_limit_enabled, rl.settings.rate_limit_requests = original_enabled, original_limit
        _reset_hits()


def test_blocks_the_request_over_the_limit_with_a_real_429():
    _reset_hits()
    from unittest.mock import MagicMock

    from fastapi import HTTPException
    import app.rate_limit as rl

    fake_request = MagicMock()
    fake_request.client.host = "5.6.7.8"

    original_enabled, original_limit = rl.settings.rate_limit_enabled, rl.settings.rate_limit_requests
    rl.settings.rate_limit_enabled = True
    rl.settings.rate_limit_requests = 2
    try:
        rate_limit(fake_request)
        rate_limit(fake_request)
        try:
            rate_limit(fake_request)
            assert False, "expected the 3rd request to be rate-limited"
        except HTTPException as exc:
            assert exc.status_code == 429
            assert "Retry-After" in exc.headers
            # A readable, specific detail — not a bare status code (this
            # codebase's own established convention, see api/client.js).
            assert "Too many requests" in exc.detail
    finally:
        rl.settings.rate_limit_enabled, rl.settings.rate_limit_requests = original_enabled, original_limit
        _reset_hits()


def test_disabled_setting_never_limits_anything():
    _reset_hits()
    from unittest.mock import MagicMock
    import app.rate_limit as rl

    fake_request = MagicMock()
    fake_request.client.host = "9.9.9.9"

    original_enabled, original_limit = rl.settings.rate_limit_enabled, rl.settings.rate_limit_requests
    rl.settings.rate_limit_enabled = False
    rl.settings.rate_limit_requests = 1
    try:
        for _ in range(10):
            rate_limit(fake_request)  # must not raise even once
    finally:
        rl.settings.rate_limit_enabled, rl.settings.rate_limit_requests = original_enabled, original_limit
        _reset_hits()


def test_different_clients_get_independent_limits():
    _reset_hits()
    from unittest.mock import MagicMock
    import app.rate_limit as rl

    request_a = MagicMock()
    request_a.client.host = "1.1.1.1"
    request_b = MagicMock()
    request_b.client.host = "2.2.2.2"

    original_enabled, original_limit = rl.settings.rate_limit_enabled, rl.settings.rate_limit_requests
    rl.settings.rate_limit_enabled = True
    rl.settings.rate_limit_requests = 1
    try:
        rate_limit(request_a)  # uses up client A's one allowed request
        rate_limit(request_b)  # client B is unaffected — must not raise
    finally:
        rl.settings.rate_limit_enabled, rl.settings.rate_limit_requests = original_enabled, original_limit
        _reset_hits()


# --------------------------------------------------------------------- #
# Integration: the real HTTP 429 on /api/chat once the limit is hit.
# --------------------------------------------------------------------- #


def test_chat_endpoint_returns_a_real_429_once_the_limit_is_hit(monkeypatch):
    _mock_resolved_chat(monkeypatch)
    customer_id = _seed_customer()

    # Same ROWID-reuse hazard test_rbac_matrix.py's fixture already
    # documents and fixes: other test files clear the shared Ticket
    # table for their own scoped needs, orphaning any Investigation row
    # that pointed at a now-deleted ticket. This test is one of the few
    # that lets /api/chat create a real Ticket via plain autoincrement
    # (most others pre-seed an explicit high id specifically to avoid
    # this), so it can collide with an orphaned Investigation's
    # ticket_id (UNIQUE) if run after one of those cleanup-heavy files.
    with SessionLocal() as cleanup_db:
        from app.db.models import Investigation, InvestigationStep, Ticket

        real_ticket_ids = {row[0] for row in cleanup_db.query(Ticket.id).all()}
        orphan_ids = [inv.id for inv in cleanup_db.query(Investigation).all() if inv.ticket_id not in real_ticket_ids]
        if orphan_ids:
            cleanup_db.query(InvestigationStep).filter(InvestigationStep.investigation_id.in_(orphan_ids)).delete(
                synchronize_session=False
            )
            cleanup_db.query(Investigation).filter(Investigation.id.in_(orphan_ids)).delete(synchronize_session=False)
            cleanup_db.commit()

    import app.rate_limit as rl
    monkeypatch.setattr(rl.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(rl.settings, "rate_limit_requests", 2)
    _reset_hits()

    try:
        r1 = client.post("/api/chat", json={"customer_id": customer_id, "message": "hi"})
        r2 = client.post("/api/chat", json={"customer_id": customer_id, "message": "hi again"})
        r3 = client.post("/api/chat", json={"customer_id": customer_id, "message": "one more"})

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429
        assert "Too many requests" in r3.json()["detail"]
    finally:
        _reset_hits()
