"""[Omnichannel] issue #162 — Demo data generation.

A real, pre-existing gap in this codebase (documented in `conftest.py`,
found again here): several other test files
(`test_analytics.py`/`test_kb_api.py`/`test_records_api.py`) legitimately
wipe the shared session-wide `Ticket` table for their own scoped needs.
Testing "does the seeded channel data still exist right now" against
that same mutable, shared DB is fragile and order-dependent — it failed
the first time this file was run as part of the full suite (passed in
isolation, failed when run after one of those files). Fixed the same way
this project's own history already fixed this exact class of bug once
(the #14/#17 conftest.py entries): test against a genuinely fresh,
isolated `seed_if_empty()` run instead, which is what the acceptance
criteria actually asks for ("a fresh seed_if_empty() run produces...").

Inbox visibility for a real channel-routed conversation is already
covered end-to-end by test_omnichannel_e2e.py (#164) — not duplicated
here against the fragile shared DB.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.db.seed as seed_module
from app.db.database import Base
from app.db.models import Ticket

_ALL_CHANNELS = {"live_chat", "email", "whatsapp", "instagram", "messenger"}


@pytest.fixture
def fresh_seeded_session(monkeypatch):
    """A genuinely fresh, isolated engine — seed_if_empty() run against
    it exactly once, untouched by anything any other test file does to
    the shared session-wide test DB."""
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


def test_fresh_seed_produces_at_least_one_real_ticket_per_channel(fresh_seeded_session):
    channels_seen = {t.channel_key for t in fresh_seeded_session.query(Ticket).all()}
    assert _ALL_CHANNELS <= channels_seen


def test_fresh_seed_non_live_chat_tickets_are_real_not_placeholder_text(fresh_seeded_session):
    non_live_chat = fresh_seeded_session.query(Ticket).filter(Ticket.channel_key != "live_chat").all()
    assert len(non_live_chat) >= 4
    for t in non_live_chat:
        assert t.message and "lorem" not in t.message.lower()
        assert t.subject


def test_fresh_seed_running_twice_does_not_duplicate_channel_tickets(fresh_seeded_session):
    """seed_if_empty()'s own existing guard (`if db.query(Customer).first(): return`)
    should make a second call a no-op — confirmed explicitly for the new
    channel-tagged tickets specifically, not just assumed to inherit the
    guard correctly."""
    before = fresh_seeded_session.query(Ticket).count()
    seed_module.seed_if_empty()
    after = fresh_seeded_session.query(Ticket).count()
    assert before == after
