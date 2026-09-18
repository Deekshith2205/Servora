"""[RAG] Phase 2/5/9 (#231-#236, #248-#252, #268-#274) — app/api/knowledge.py
over the real shared test DB + a real (isolated) ChromaDB directory (see
conftest.py's CHROMA_PERSIST_DIR/UPLOAD_DIR overrides). Embeddings are
mocked at the module boundary — the real Gemini call needs a live key,
same convention as every other test in this codebase that mocks the LLM
client rather than hitting a real provider.

[RBAC]: read (list/detail/search) needs `view_knowledge_base` (Support
Agent, Manager, Administrator); write (upload/delete/reprocess) needs
`manage_knowledge_base` (Administrator only) — every test sends a real
identity header, per this codebase's own RBAC test convention.
"""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.db.models import KnowledgeChunk, KnowledgeDocument, KnowledgeSearchLog
from app.main import app
from app.services import vector_store
from tests.rbac_headers import customer_headers, staff_headers


def _clear_knowledge(db):
    db.query(KnowledgeSearchLog).delete()
    db.query(KnowledgeChunk).delete()
    db.query(KnowledgeDocument).delete()
    db.commit()
    vector_store.reset_for_tests()


def _fake_embed_texts(texts, task_type="RETRIEVAL_DOCUMENT"):
    return [[float(hash((t, i)) % 997) for i in range(8)] for t in texts]


def _fake_embed_text(text, task_type="RETRIEVAL_QUERY"):
    return _fake_embed_texts([text], task_type=task_type)[0]


def test_upload_requires_manage_knowledge_base_permission():
    with SessionLocal() as db:
        _clear_knowledge(db)
        headers = staff_headers(db, "support_agent")  # has view_, not manage_
        with TestClient(app) as client:
            resp = client.post(
                "/api/knowledge/documents",
                headers=headers,
                files={"file": ("policy.txt", b"Some policy text.", "text/plain")},
            )
    assert resp.status_code == 403


def test_upload_rejects_unauthenticated_caller():
    with TestClient(app) as client:
        resp = client.post(
            "/api/knowledge/documents",
            files={"file": ("policy.txt", b"Some policy text.", "text/plain")},
        )
    assert resp.status_code == 403


def test_customer_cannot_reach_any_knowledge_endpoint():
    with SessionLocal() as db:
        _clear_knowledge(db)
    with TestClient(app) as client:
        headers = customer_headers(1)
        assert client.get("/api/knowledge/documents", headers=headers).status_code == 403
        assert client.get("/api/knowledge/search?q=refund", headers=headers).status_code == 403


def test_upload_then_list_then_detail_reach_indexed_status():
    with SessionLocal() as db:
        _clear_knowledge(db)
        headers = staff_headers(db, "administrator")

    with patch("app.services.knowledge_retrieval.embed_texts", side_effect=_fake_embed_texts):
        with TestClient(app) as client:
            upload_resp = client.post(
                "/api/knowledge/documents",
                headers=headers,
                params={"title": "Refund Policy"},
                files={"file": ("refund.txt", b"Refunds are accepted within 30 days of purchase.", "text/plain")},
            )
            assert upload_resp.status_code == 200
            body = upload_resp.json()
            assert body["title"] == "Refund Policy"
            assert body["status"] in ("uploaded", "processing", "indexed")
            doc_id = body["id"]

            list_resp = client.get("/api/knowledge/documents", headers=headers)
            assert list_resp.status_code == 200
            listed = [d for d in list_resp.json() if d["id"] == doc_id]
            assert len(listed) == 1
            assert listed[0]["status"] == "indexed"
            assert listed[0]["chunk_count"] == 1

            detail_resp = client.get(f"/api/knowledge/documents/{doc_id}", headers=headers)
            assert detail_resp.status_code == 200
            detail = detail_resp.json()
            assert detail["status"] == "indexed"
            assert len(detail["chunks"]) == 1
            assert "30 days" in detail["chunks"][0]["text"]


def test_view_knowledge_base_permission_allows_support_agent_and_manager_read():
    with SessionLocal() as db:
        _clear_knowledge(db)
    with TestClient(app) as client:
        for role in ("support_agent", "manager", "administrator"):
            with SessionLocal() as db:
                headers = staff_headers(db, role)
            resp = client.get("/api/knowledge/documents", headers=headers)
            assert resp.status_code == 200, f"{role} should be able to list documents"


def test_search_returns_real_results_and_gates_by_permission():
    with SessionLocal() as db:
        _clear_knowledge(db)
        admin_headers = staff_headers(db, "administrator")
        agent_headers = staff_headers(db, "support_agent")

    with patch("app.services.knowledge_retrieval.embed_texts", side_effect=_fake_embed_texts):
        with TestClient(app) as client:
            client.post(
                "/api/knowledge/documents",
                headers=admin_headers,
                params={"title": "Shipping Policy"},
                files={"file": ("shipping.txt", b"Standard shipping takes 5 to 7 business days.", "text/plain")},
            )

    with patch("app.services.knowledge_retrieval.embed_text", side_effect=_fake_embed_text):
        with TestClient(app) as client:
            resp = client.get("/api/knowledge/search", headers=agent_headers, params={"q": "how long is shipping"})
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["document_title"] == "Shipping Policy"
    assert "business days" in results[0]["text"]


def test_search_requires_a_permission_that_support_agent_lacks_returns_403_for_customer():
    with SessionLocal() as db:
        _clear_knowledge(db)
    with TestClient(app) as client:
        resp = client.get("/api/knowledge/search", headers=customer_headers(1), params={"q": "anything"})
    assert resp.status_code == 403


def test_delete_document_is_admin_only_and_actually_removes_it():
    with SessionLocal() as db:
        _clear_knowledge(db)
        admin_headers = staff_headers(db, "administrator")
        agent_headers = staff_headers(db, "support_agent")

    with patch("app.services.knowledge_retrieval.embed_texts", side_effect=_fake_embed_texts):
        with TestClient(app) as client:
            upload = client.post(
                "/api/knowledge/documents",
                headers=admin_headers,
                params={"title": "Delete Test"},
                files={"file": ("delete.txt", b"Temporary content for a delete test.", "text/plain")},
            )
            doc_id = upload.json()["id"]

            forbidden = client.delete(f"/api/knowledge/documents/{doc_id}", headers=agent_headers)
            assert forbidden.status_code == 403

            deleted = client.delete(f"/api/knowledge/documents/{doc_id}", headers=admin_headers)
            assert deleted.status_code == 200

            missing = client.get(f"/api/knowledge/documents/{doc_id}", headers=admin_headers)
            assert missing.status_code == 404


def test_reprocess_resets_and_reindexes_a_document():
    with SessionLocal() as db:
        _clear_knowledge(db)
        admin_headers = staff_headers(db, "administrator")

    with patch("app.services.knowledge_retrieval.embed_texts", side_effect=_fake_embed_texts):
        with TestClient(app) as client:
            upload = client.post(
                "/api/knowledge/documents",
                headers=admin_headers,
                params={"title": "Reprocess Test"},
                files={"file": ("reprocess.txt", b"Content that will be reprocessed.", "text/plain")},
            )
            doc_id = upload.json()["id"]

            # reprocess_document() resets status to "uploaded" BEFORE
            # scheduling the background re-index task — the response
            # body is built from that pre-reindex snapshot (same honest
            # "kicked off, not complete yet" contract as the upload
            # endpoint's own response), even though the background task
            # has genuinely finished re-indexing the real DB row by the
            # time this call returns (confirmed via the follow-up GET).
            reprocess = client.post(f"/api/knowledge/documents/{doc_id}/reprocess", headers=admin_headers)
            assert reprocess.status_code == 200
            assert reprocess.json()["status"] == "uploaded"

            after = client.get(f"/api/knowledge/documents/{doc_id}", headers=admin_headers)
            assert after.json()["status"] == "indexed"


def test_upload_of_unsupported_file_type_returns_400():
    with SessionLocal() as db:
        _clear_knowledge(db)
        admin_headers = staff_headers(db, "administrator")
    with TestClient(app) as client:
        resp = client.post(
            "/api/knowledge/documents",
            headers=admin_headers,
            files={"file": ("malware.exe", b"binary content", "application/octet-stream")},
        )
    assert resp.status_code == 400


def test_get_missing_document_returns_404():
    with SessionLocal() as db:
        _clear_knowledge(db)
        admin_headers = staff_headers(db, "administrator")
    with TestClient(app) as client:
        resp = client.get("/api/knowledge/documents/999999", headers=admin_headers)
    assert resp.status_code == 404
