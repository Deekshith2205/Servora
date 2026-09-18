"""[RAG] Phase 6/7 (#253-#262) — the `search_knowledge` tool wired into
the specialist tool-calling pipeline: exposed to billing/technical/order
(never account, matching search_kb's own boundary), producing real
Investigation Board evidence strings and structured `knowledge_chunk`
evidence_refs from the actual search result — never placeholder text.

Mocks `app.tools.tool_registry.search_knowledge` (the one real call
site `_call_search_knowledge` wraps) rather than the Anthropic client's
embedding call — the real semantic-search logic is already covered in
test_knowledge_service.py; this file proves the TOOL WIRING is correct.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Customer
from app.services.embeddings import EmbeddingError
from app.tools.tool_registry import (
    SPECIALIST_TOOL_PERMISSIONS,
    _call_search_knowledge,
    build_filtered_tool_registry,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _tool_use(id_, name, input_):
    block = MagicMock()
    block.type, block.id, block.name, block.input = "tool_use", id_, name, input_
    return block


def _text(text):
    block = MagicMock()
    block.type, block.text = "text", text
    return block


def _response(content, stop_reason):
    resp = MagicMock()
    resp.content, resp.stop_reason = content, stop_reason
    return resp


def test_search_knowledge_is_in_billing_technical_and_order_but_not_account():
    assert "search_knowledge" in SPECIALIST_TOOL_PERMISSIONS["billing"]
    assert "search_knowledge" in SPECIALIST_TOOL_PERMISSIONS["technical"]
    assert "search_knowledge" in SPECIALIST_TOOL_PERMISSIONS["order"]
    assert "search_knowledge" not in SPECIALIST_TOOL_PERMISSIONS["account"]


def test_account_specialist_never_receives_the_search_knowledge_schema(db_session):
    schemas, handlers = build_filtered_tool_registry(db_session, "account")
    names = {s["name"] for s in schemas}
    assert "search_knowledge" not in names
    assert "search_knowledge" not in handlers


def test_call_search_knowledge_wraps_a_real_result(db_session):
    fake_hits = [
        {"chunk_id": 5, "document_id": 2, "document_title": "Warranty Policy", "text": "1-year warranty.", "score": 0.87}
    ]
    with patch("app.tools.tool_registry.search_knowledge", return_value=fake_hits):
        result = _call_search_knowledge(db_session, "warranty terms")
    assert result == {"results": fake_hits}


def test_call_search_knowledge_degrades_honestly_on_embedding_failure(db_session):
    with patch("app.tools.tool_registry.search_knowledge", side_effect=EmbeddingError("no key configured")):
        result = _call_search_knowledge(db_session, "warranty terms")
    assert result["results"] == []
    assert "no key configured" in result["error"]


def test_technical_specialist_records_real_evidence_and_evidence_refs_from_search_knowledge(db_session):
    from app.agents.specialists import resolve_technical

    customer = Customer(name="Dana Kim", email="dana-rag-test@example.com", tier="standard")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    fake_hits = [
        {"chunk_id": 11, "document_id": 3, "document_title": "Troubleshooting Guide", "text": "Restart the app and clear cache.", "score": 0.93},
    ]
    responses = [
        _response([_tool_use("t1", "search_knowledge", {"query": "app crashing"})], "tool_use"),
        _response([_text("Please restart the app and clear its cache — this resolves the crash in most cases.")], "end_turn"),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("app.llm.get_client", return_value=mock_client), \
         patch("app.tools.tool_registry.search_knowledge", return_value=fake_hits):
        result = resolve_technical(db_session, customer.id, "The app keeps crashing")

    assert "search_knowledge" in result.used_tools
    assert result.confidence == 0.6  # grounding tier, no action tool
    assert any("Knowledge Center" in e and "Troubleshooting Guide" in e for e in result.evidence)
    knowledge_refs = [r for r in result.evidence_refs if r["type"] == "knowledge_chunk"]
    assert len(knowledge_refs) == 1
    assert knowledge_refs[0]["ref_id"] == 11
    assert "Troubleshooting Guide" in knowledge_refs[0]["label"]
    assert "93%" in knowledge_refs[0]["label"]


def test_specialist_records_honest_evidence_when_search_knowledge_finds_nothing(db_session):
    from app.agents.specialists import resolve_technical

    customer = Customer(name="Eli Frost", email="eli-rag-test@example.com", tier="standard")
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    responses = [
        _response([_tool_use("t1", "search_knowledge", {"query": "obscure feature"})], "tool_use"),
        _response([_text("I couldn't find documentation on this — a human agent will need to help.")], "end_turn"),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = responses

    with patch("app.llm.get_client", return_value=mock_client), \
         patch("app.tools.tool_registry.search_knowledge", return_value=[]):
        result = resolve_technical(db_session, customer.id, "How do I use the obscure feature?")

    assert "search_knowledge" in result.used_tools
    assert any("no matching passages found" in e for e in result.evidence)
    assert [r for r in result.evidence_refs if r["type"] == "knowledge_chunk"] == []
