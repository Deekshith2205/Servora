"""[Omnichannel] issue #132 — the Channel model and its seed data.

Uses the shared session-wide test DB (conftest.py already runs
seed_if_empty() against it once, before any test module is even
imported) rather than building a second isolated DB and re-seeding,
since the acceptance criteria is specifically about what a real
seed_if_empty() run produces.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.db.database import SessionLocal
from app.db.models import Channel

_EXPECTED_KEYS = {"live_chat", "email", "whatsapp", "instagram", "messenger"}


def test_seed_creates_exactly_the_five_channels():
    db = SessionLocal()
    try:
        channels = db.query(Channel).all()
        assert {c.key for c in channels} == _EXPECTED_KEYS
        assert len(channels) == 5
    finally:
        db.close()


def test_live_chat_seeds_active_every_other_channel_seeds_not_configured():
    """Live Chat is the one channel with real, working transport today
    (the existing /api/chat path) — everything else is honestly
    "not_configured" rather than a fabricated "active"."""
    db = SessionLocal()
    try:
        by_key = {c.key: c for c in db.query(Channel).all()}
        assert by_key["live_chat"].status == "active"
        for key in _EXPECTED_KEYS - {"live_chat"}:
            assert by_key[key].status == "not_configured"
    finally:
        db.close()


def test_channel_row_with_only_key_set_does_not_error():
    db = SessionLocal()
    try:
        channel = Channel(key="__test_only_key__")
        db.add(channel)
        db.commit()
        db.refresh(channel)

        assert channel.display_name == ""
        assert channel.status == "not_configured"
        assert channel.config == {}
        assert channel.created_at is not None
        assert channel.updated_at is not None
    finally:
        db.query(Channel).filter(Channel.key == "__test_only_key__").delete()
        db.commit()
        db.close()


def test_config_property_parses_config_json():
    db = SessionLocal()
    try:
        channel = Channel(key="__test_config_channel__", config_json='{"webhook_url": "https://example.com/hook"}')
        db.add(channel)
        db.commit()
        db.refresh(channel)

        assert channel.config == {"webhook_url": "https://example.com/hook"}
    finally:
        db.query(Channel).filter(Channel.key == "__test_config_channel__").delete()
        db.commit()
        db.close()


def test_channel_key_must_be_unique():
    """`key` is the stable slug Ticket.channel_key/Investigation.channel_key
    (issue #133) and the future channel-status API (issue #135) will look
    rows up by — a duplicate would make "the channel" ambiguous. Enforced
    at the DB level (`unique=True`), not just by convention, so this locks
    in real protection rather than just documenting an assumption."""
    db = SessionLocal()
    try:
        db.add(Channel(key="whatsapp", display_name="Duplicate WhatsApp"))
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()
