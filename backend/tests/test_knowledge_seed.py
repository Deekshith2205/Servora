"""[RAG] issue #225 Phase 11 (#280/#281) — seed_knowledge_documents_if_missing().

Runs against a fresh isolated in-memory engine (same pattern
test_payment_scenario_seeding.py already established) with a real,
isolated CHROMA_PERSIST_DIR (conftest.py) and embeddings mocked — the
SEED_KNOWLEDGE_DOCUMENTS=false override conftest.py sets globally is
explicitly re-enabled per-test here via monkeypatch, since this file's
whole point is testing that gated path.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.db.seed as seed_module
from app.db.database import Base
from app.db.models import KnowledgeDocument
from app.services import vector_store


def _fake_embed_texts(texts, task_type="RETRIEVAL_DOCUMENT"):
    return [[float(hash((t, i)) % 997) for i in range(8)] for t in texts]


@pytest.fixture
def fresh_seeded_session(monkeypatch, tmp_path):
    monkeypatch.setenv("SEED_KNOWLEDGE_DOCUMENTS", "true")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    vector_store.reset_for_tests()

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    fresh_session_local = sessionmaker(bind=engine)
    monkeypatch.setattr(seed_module, "SessionLocal", fresh_session_local)
    monkeypatch.setattr("app.services.knowledge_retrieval.SessionLocal", fresh_session_local)

    with patch("app.services.knowledge_retrieval.embed_texts", side_effect=_fake_embed_texts):
        seed_module.seed_if_empty()

    session = fresh_session_local()
    try:
        yield session
    finally:
        session.close()
        vector_store.reset_for_tests()


def test_fresh_seed_indexes_all_three_policy_documents(fresh_seeded_session):
    documents = fresh_seeded_session.query(KnowledgeDocument).all()
    titles = {d.title for d in documents}
    assert titles == {
        "Refund & Return Policy",
        "Shipping & Delivery Policy",
        "Warranty & Product Support Policy",
    }
    for d in documents:
        assert d.status == "indexed"
        assert d.chunk_count > 0


def test_seed_knowledge_documents_is_idempotent(fresh_seeded_session):
    with patch("app.services.knowledge_retrieval.embed_texts", side_effect=_fake_embed_texts):
        seed_module.seed_knowledge_documents_if_missing(fresh_seeded_session)
    assert fresh_seeded_session.query(KnowledgeDocument).count() == 3


def test_seed_knowledge_documents_is_a_noop_when_gate_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("SEED_KNOWLEDGE_DOCUMENTS", "false")
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        seed_module.seed_knowledge_documents_if_missing(session)
        assert session.query(KnowledgeDocument).count() == 0
    finally:
        session.close()
