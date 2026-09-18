"""[RAG] Phase 10 (#275-#279) — compute_knowledge_metrics(), and
[Future Scope] issue #300 — compute_resolution_time_and_agent_success().
Both are pure aggregation functions over real rows (KnowledgeSearchLog/
KnowledgeDocument, Ticket) — no LLM call, no mocking needed.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.analytics import compute_knowledge_metrics, compute_resolution_time_and_agent_success
from app.db.database import Base
from app.db.models import Customer, KnowledgeDocument, KnowledgeSearchLog, Ticket


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def test_knowledge_metrics_are_all_honest_zeros_with_nothing_logged(db_session):
    cutoff = datetime.utcnow() - timedelta(days=30)
    metrics = compute_knowledge_metrics(db_session, cutoff)
    assert metrics["usage"]["total_searches"] == 0
    assert metrics["success_rate"] == 0.0
    assert metrics["most_used_documents"] == []
    assert metrics["coverage"]["total_documents"] == 0
    assert metrics["performance"]["avg_duration_ms"] is None
    assert metrics["performance"]["avg_top_score"] is None


def test_knowledge_metrics_compute_real_usage_and_success_rate(db_session):
    doc = KnowledgeDocument(
        title="Refund Policy", filename="r.txt", file_path="/tmp/r.txt", file_type="txt",
        status="indexed", chunk_count=3,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    now = datetime.utcnow()
    db_session.add_all([
        KnowledgeSearchLog(query="refund window", result_count=2, top_document_id=doc.id, top_score=0.9, duration_ms=120, created_at=now),
        KnowledgeSearchLog(query="refund window", result_count=1, top_document_id=doc.id, top_score=0.8, duration_ms=80, created_at=now),
        KnowledgeSearchLog(query="nonexistent topic", result_count=0, top_document_id=None, top_score=None, duration_ms=60, created_at=now),
    ])
    db_session.commit()

    cutoff = now - timedelta(days=30)
    metrics = compute_knowledge_metrics(db_session, cutoff)

    assert metrics["usage"]["total_searches"] == 3
    assert metrics["success_rate"] == pytest.approx(2 / 3)
    assert metrics["coverage"]["total_documents"] == 1
    assert metrics["coverage"]["total_chunks"] == 3
    assert metrics["coverage"]["by_status"] == {"indexed": 1}
    assert metrics["performance"]["avg_duration_ms"] == pytest.approx((120 + 80 + 60) / 3)
    assert metrics["performance"]["avg_top_score"] == pytest.approx((0.9 + 0.8) / 2)
    assert len(metrics["most_used_documents"]) == 1
    assert metrics["most_used_documents"][0]["hit_count"] == 2
    assert metrics["most_used_documents"][0]["title"] == "Refund Policy"


def test_knowledge_metrics_excludes_searches_outside_the_cutoff_window(db_session):
    old = datetime.utcnow() - timedelta(days=45)
    db_session.add(KnowledgeSearchLog(query="stale", result_count=1, duration_ms=10, created_at=old))
    db_session.commit()

    cutoff = datetime.utcnow() - timedelta(days=30)
    metrics = compute_knowledge_metrics(db_session, cutoff)
    assert metrics["usage"]["total_searches"] == 0


def _customer(db):
    c = Customer(name="Test Customer", email="rag-analytics@example.com", tier="standard")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_resolution_time_and_agent_success_reports_none_with_no_resolved_tickets(db_session):
    cutoff = datetime.utcnow() - timedelta(days=30)
    result = compute_resolution_time_and_agent_success(db_session, cutoff)
    assert result["avg_resolution_time_seconds"] is None
    assert result["resolved_ticket_count"] == 0
    assert result["agent_success_rate"] == []


def test_resolution_time_and_agent_success_computes_real_duration_and_per_agent_rate(db_session):
    customer = _customer(db_session)
    now = datetime.utcnow()

    t1 = Ticket(
        customer_id=customer.id, category="billing", subject="s1", message="m1",
        status="resolved", created_at=now - timedelta(hours=2), resolved_at=now - timedelta(hours=1),
        assigned_to=None,  # AI (autonomous)
    )
    t2 = Ticket(
        customer_id=customer.id, category="technical", subject="s2", message="m2",
        status="resolved", created_at=now - timedelta(hours=4), resolved_at=now - timedelta(hours=3, minutes=30),
        assigned_to="Jordan Lee",
    )
    t3 = Ticket(
        customer_id=customer.id, category="technical", subject="s3", message="m3",
        status="escalated", created_at=now - timedelta(hours=1), assigned_to="Jordan Lee",
    )
    db_session.add_all([t1, t2, t3])
    db_session.commit()

    cutoff = now - timedelta(days=30)
    result = compute_resolution_time_and_agent_success(db_session, cutoff)

    assert result["resolved_ticket_count"] == 2
    expected_avg = ((1 * 3600) + (0.5 * 3600)) / 2
    assert result["avg_resolution_time_seconds"] == pytest.approx(expected_avg, rel=0.01)

    by_agent = {a["agent"]: a for a in result["agent_success_rate"]}
    assert by_agent["AI (autonomous)"] == {"agent": "AI (autonomous)", "resolved": 1, "total": 1, "success_rate": 1.0}
    assert by_agent["Jordan Lee"]["total"] == 2
    assert by_agent["Jordan Lee"]["resolved"] == 1
    assert by_agent["Jordan Lee"]["success_rate"] == pytest.approx(0.5)
