"""[RAG] Phases 1-5 (#226-#252) — document_processing.py (extract/clean/
chunk) and knowledge_retrieval.py (create_document -> process ->
search_knowledge). Embeddings are mocked (the real Gemini call needs a
live key, same convention as `call_llm()` tests mocking the Anthropic
client); ChromaDB itself runs for real against the isolated
CHROMA_PERSIST_DIR conftest.py sets up — proving the real vector-store
add/query/delete logic, not just the mock.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from app.db.database import Base
from app.db.models import KnowledgeChunk, KnowledgeDocument, KnowledgeSearchLog
from app.services import knowledge_retrieval, vector_store
from app.services.document_processing import (
    UnsupportedFileTypeError,
    chunk_segments,
    clean_text,
    extract_segments,
)
from app.services.embeddings import EmbeddingError
from app.services.knowledge_retrieval import EmptyFileError, FileTooLargeError


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    vector_store.reset_for_tests()
    try:
        yield session
    finally:
        session.close()
        vector_store.reset_for_tests()


def _fake_embed_texts(texts, task_type="RETRIEVAL_DOCUMENT"):
    # Deterministic, distinguishable fake vectors — good enough for a
    # real cosine-similarity query to rank correctly in tests.
    return [[float(hash((t, i)) % 997) for i in range(8)] for t in texts]


def _fake_embed_text(text, task_type="RETRIEVAL_QUERY"):
    return _fake_embed_texts([text], task_type=task_type)[0]


# --------------------------------------------------------------------- #
# document_processing.py — extraction/cleaning/chunking
# --------------------------------------------------------------------- #


def test_extract_txt_returns_one_segment_with_no_page_or_heading(tmp_path):
    f = tmp_path / "policy.txt"
    f.write_text("Our refund policy allows returns within 30 days.")
    segments = extract_segments(str(f), "txt")
    assert len(segments) == 1
    assert segments[0].page_number is None
    assert segments[0].section_heading is None
    assert "30 days" in segments[0].text


def test_extract_segments_rejects_unsupported_file_type(tmp_path):
    f = tmp_path / "policy.xyz"
    f.write_text("irrelevant")
    with pytest.raises(UnsupportedFileTypeError):
        extract_segments(str(f), "xyz")


def test_clean_text_strips_control_chars_and_collapses_whitespace():
    dirty = "Hello\x00World   with\t\tmulti   spaces\n\n\n\nand blank lines"
    cleaned = clean_text(dirty)
    assert "\x00" not in cleaned
    assert "   " not in cleaned
    assert "\n\n\n" not in cleaned


def test_chunk_segments_splits_long_text_with_overlap():
    from app.services.document_processing import Segment

    long_text = ("Paragraph one about refunds. " * 50) + "\n\n" + ("Paragraph two about shipping. " * 50)
    segments = [Segment(text=long_text, page_number=1, section_heading="Policies")]
    chunks = chunk_segments(segments, chunk_size=200, overlap=30)
    assert len(chunks) > 1
    for c in chunks:
        assert c.page_number == 1
        assert c.section_heading == "Policies"
        assert c.char_start < c.char_end


def test_chunk_segments_returns_single_chunk_for_short_text():
    from app.services.document_processing import Segment

    segments = [Segment(text="A short policy note.", page_number=None, section_heading=None)]
    chunks = chunk_segments(segments)
    assert len(chunks) == 1
    assert chunks[0].text == "A short policy note."


# --------------------------------------------------------------------- #
# knowledge_retrieval.py — create_document validation
# --------------------------------------------------------------------- #


def test_create_document_rejects_unsupported_file_type(db_session, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(UnsupportedFileTypeError):
        knowledge_retrieval.create_document(
            db_session, title="t", filename="x.exe", file_type="exe", content=b"data"
        )


def test_create_document_rejects_empty_file(db_session, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(EmptyFileError):
        knowledge_retrieval.create_document(
            db_session, title="t", filename="x.txt", file_type="txt", content=b""
        )


def test_create_document_rejects_oversized_file(db_session, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileTooLargeError):
        knowledge_retrieval.create_document(
            db_session,
            title="t",
            filename="x.txt",
            file_type="txt",
            content=b"a" * (knowledge_retrieval.MAX_FILE_SIZE_BYTES + 1),
        )


def test_create_document_persists_a_real_row_in_uploaded_status(db_session, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    doc = knowledge_retrieval.create_document(
        db_session, title="Refund Policy", filename="refund.txt", file_type="txt", content=b"Refunds within 30 days."
    )
    assert doc.id is not None
    assert doc.status == "uploaded"
    assert doc.title == "Refund Policy"
    assert doc.chunk_count == 0


# --------------------------------------------------------------------- #
# knowledge_retrieval.py — the real pipeline, embeddings mocked
# --------------------------------------------------------------------- #


def test_process_document_task_indexes_a_real_txt_document(db_session, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    doc = knowledge_retrieval.create_document(
        db_session,
        title="Warranty Policy",
        filename="warranty.txt",
        file_type="txt",
        content=b"All products carry a 1-year warranty against manufacturing defects.",
    )

    with patch("app.services.knowledge_retrieval.SessionLocal", return_value=db_session), \
         patch("app.services.knowledge_retrieval.embed_texts", side_effect=_fake_embed_texts):
        # process_document_task closes the session at the end via db.close();
        # patch close() to a no-op so the fixture's own session stays usable.
        with patch.object(db_session, "close", lambda: None):
            knowledge_retrieval.process_document_task(doc.id)

    db_session.refresh(doc)
    assert doc.status == "indexed"
    assert doc.chunk_count == 1
    assert doc.indexed_at is not None
    chunks = db_session.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).all()
    assert len(chunks) == 1
    assert chunks[0].embedding_id == f"chunk-{chunks[0].id}"


def test_process_document_task_marks_failed_on_empty_extraction(db_session, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # A .txt file that becomes empty after saving is unrealistic via
    # create_document (it rejects empty content up front) — simulate the
    # "no extractable text" failure path directly via a PDF stub instead:
    # write a real KnowledgeDocument row pointing at a file whose
    # extraction will legitimately produce zero segments (blank content
    # after whitespace-only text).
    doc = KnowledgeDocument(
        title="Blank", filename="blank.txt", file_path=str(tmp_path / "blank.txt"),
        file_type="txt", file_size_bytes=1, status="uploaded",
    )
    (tmp_path / "blank.txt").write_text("   \n\n   ")
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    with patch("app.services.knowledge_retrieval.SessionLocal", return_value=db_session):
        with patch.object(db_session, "close", lambda: None):
            knowledge_retrieval.process_document_task(doc.id)

    db_session.refresh(doc)
    assert doc.status == "failed"
    assert doc.error_message is not None


def test_search_knowledge_returns_empty_for_blank_query(db_session):
    assert knowledge_retrieval.search_knowledge(db_session, "   ") == []


def test_search_knowledge_returns_empty_when_nothing_indexed(db_session):
    with patch("app.services.knowledge_retrieval.embed_text", side_effect=_fake_embed_text):
        assert knowledge_retrieval.search_knowledge(db_session, "refund window") == []


def _index_one_document(db_session, tmp_path, monkeypatch, *, title, filename, content):
    monkeypatch.chdir(tmp_path)
    doc = knowledge_retrieval.create_document(
        db_session, title=title, filename=filename, file_type="txt", content=content
    )
    with patch("app.services.knowledge_retrieval.SessionLocal", return_value=db_session), \
         patch("app.services.knowledge_retrieval.embed_texts", side_effect=_fake_embed_texts):
        with patch.object(db_session, "close", lambda: None):
            knowledge_retrieval.process_document_task(doc.id)
    db_session.refresh(doc)
    return doc


def test_search_knowledge_returns_real_indexed_chunk_and_logs_the_search(db_session, tmp_path, monkeypatch):
    doc = _index_one_document(
        db_session, tmp_path, monkeypatch,
        title="Shipping Policy", filename="shipping.txt",
        content=b"Standard shipping takes 5-7 business days from order confirmation.",
    )
    assert doc.status == "indexed"

    with patch("app.services.knowledge_retrieval.embed_text", side_effect=_fake_embed_text):
        results = knowledge_retrieval.search_knowledge(db_session, "how long does shipping take")

    assert len(results) == 1
    assert results[0]["document_id"] == doc.id
    assert results[0]["document_title"] == "Shipping Policy"
    assert "business days" in results[0]["text"]
    assert 0.0 <= results[0]["score"] <= 1.0

    logs = db_session.query(KnowledgeSearchLog).all()
    assert len(logs) == 1
    assert logs[0].result_count == 1
    assert logs[0].top_document_id == doc.id
    assert logs[0].top_score is not None
    assert logs[0].duration_ms >= 0


def test_search_knowledge_excludes_chunks_from_non_indexed_documents(db_session, tmp_path, monkeypatch):
    doc = _index_one_document(
        db_session, tmp_path, monkeypatch,
        title="Old Policy", filename="old.txt", content=b"A stale policy about returns.",
    )
    # Simulate a document mid-reprocessing: SQL status flips away from
    # "indexed" while a vector-store entry still exists for a moment —
    # search_knowledge's own documented filter must exclude it.
    doc.status = "processing"
    db_session.commit()

    with patch("app.services.knowledge_retrieval.embed_text", side_effect=_fake_embed_text):
        results = knowledge_retrieval.search_knowledge(db_session, "returns policy")
    assert results == []


def test_reprocess_document_clears_chunks_and_vectors_and_resets_status(db_session, tmp_path, monkeypatch):
    doc = _index_one_document(
        db_session, tmp_path, monkeypatch,
        title="Return Policy", filename="return.txt", content=b"Returns accepted within 14 days of delivery.",
    )
    assert doc.chunk_count == 1

    knowledge_retrieval.reprocess_document(db_session, doc)
    db_session.refresh(doc)
    assert doc.status == "uploaded"
    assert doc.chunk_count == 0
    assert doc.indexed_at is None
    assert db_session.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).count() == 0
    assert vector_store.query([0.0] * 8, n_results=5) == []


def test_delete_document_removes_row_chunks_and_file(db_session, tmp_path, monkeypatch):
    doc = _index_one_document(
        db_session, tmp_path, monkeypatch,
        title="Delete Me", filename="delete.txt", content=b"Temporary content to be deleted.",
    )
    file_path = doc.file_path
    import os
    assert os.path.exists(file_path)

    knowledge_retrieval.delete_document(db_session, doc)

    assert db_session.get(KnowledgeDocument, doc.id) is None
    assert not os.path.exists(file_path)
    assert vector_store.query([0.0] * 8, n_results=5) == []


def test_search_knowledge_propagates_embedding_error(db_session, tmp_path, monkeypatch):
    _index_one_document(
        db_session, tmp_path, monkeypatch,
        title="Any Policy", filename="any.txt", content=b"Some policy text.",
    )
    with patch("app.services.knowledge_retrieval.embed_text", side_effect=EmbeddingError("no key configured")):
        with pytest.raises(EmbeddingError):
            knowledge_retrieval.search_knowledge(db_session, "policy question")
