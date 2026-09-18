"""[RAG] Phase 2 (#231-#236 ingestion), Phase 3 (#237-#241 processing),
Phase 5 (#248-#252 retrieval) — the orchestration layer tying together
`document_processing.py` (extract/clean/chunk), `embeddings.py`
(Gemini), and `vector_store.py` (ChromaDB) into the two real operations
everything else in this epic calls:

- `create_document()` + `process_document_task()` — upload -> indexed.
- `search_knowledge()` — a real semantic search over indexed chunks,
  the function the [RAG] #253 `search_knowledge` tool and the Knowledge
  Center's own search interface (#272) both call.

`process_document_task()` runs in a FastAPI `BackgroundTasks` context —
AFTER the response is already sent — so it deliberately opens its OWN
`SessionLocal()` rather than reusing the request's `db` session, the
exact same "each background/isolated unit of work gets its own
session, never the request's shared one" convention `app/orchestrator.py`
already established for the [SWARM] #88 parallel-specialist fan-out
(`_run_specialist_isolated()`) — a request-scoped session is closed by
`get_db()`'s own teardown and isn't safe to keep using once the
response has gone out.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import KnowledgeChunk, KnowledgeDocument, KnowledgeSearchLog
from app.services import vector_store
from app.services.document_processing import (
    SUPPORTED_FILE_TYPES,
    UnsupportedFileTypeError,
    chunk_segments,
    extract_segments,
)
from app.services.embeddings import EmbeddingError, embed_text, embed_texts

# [RAG] #235 — file size handling: 20 MB is generous for a real policy/
# manual/SOP document (this codebase's own demo documents are a few KB)
# while still bounding a single upload's processing time and memory use.
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024


def _upload_dir() -> str:
    """Read lazily, not a module-level constant — same
    `CHROMA_PERSIST_DIR`/`DATABASE_URL` test-isolation convention (see
    `app/services/vector_store.py::_persist_dir()`), so running `pytest`
    never writes real uploaded-file bytes into the local dev server's
    actual `backend/uploads/` directory."""
    return os.environ.get("UPLOAD_DIR", "uploads")


class FileTooLargeError(ValueError):
    """[RAG] #235."""


class EmptyFileError(ValueError):
    """[RAG] #236 — an honest, specific error rather than a confusing
    downstream "no extractable text" failure once processing runs."""


def _save_upload(filename: str, content: bytes) -> str:
    upload_dir = _upload_dir()
    os.makedirs(upload_dir, exist_ok=True)
    # A random stored name, never the original filename, sidesteps path
    # traversal and collision entirely — the original name is preserved
    # separately as KnowledgeDocument.filename for display.
    ext = os.path.splitext(filename)[1]
    stored_name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(upload_dir, stored_name)
    with open(path, "wb") as f:
        f.write(content)
    return path


def create_document(
    db: Session, *, title: str, filename: str, file_type: str, content: bytes
) -> KnowledgeDocument:
    """[RAG] #231/#232/#233/#234/#235/#236 — validates and persists one
    uploaded file's metadata row (status="uploaded"). Does NOT process
    it — the caller (POST /api/knowledge/documents) schedules
    `process_document_task()` as a background task once this returns,
    so the request itself returns immediately with a real, honest
    "uploaded, not yet indexed" status.
    """
    file_type = file_type.lower().lstrip(".")
    if file_type not in SUPPORTED_FILE_TYPES:
        raise UnsupportedFileTypeError(
            f"Unsupported file type {file_type!r} — must be one of {sorted(SUPPORTED_FILE_TYPES)}."
        )
    if not content:
        raise EmptyFileError("Uploaded file is empty.")
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise FileTooLargeError(
            f"File is {len(content)} bytes, which exceeds the {MAX_FILE_SIZE_BYTES}-byte limit."
        )

    file_path = _save_upload(filename, content)
    document = KnowledgeDocument(
        title=title.strip() or filename,
        filename=filename,
        file_path=file_path,
        file_type=file_type,
        file_size_bytes=len(content),
        status="uploaded",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def process_document_task(document_id: int) -> None:
    """[RAG] #237-#241 — the real extract -> clean -> chunk -> embed ->
    store pipeline, run against a fresh session (see module docstring).
    Always leaves the document in a terminal, honest state: "indexed"
    with a real `chunk_count`/`indexed_at`, or "failed" with a real
    `error_message` — never left silently stuck on "processing" if
    something throws.
    """
    db = SessionLocal()
    try:
        document = db.get(KnowledgeDocument, document_id)
        if document is None:
            return
        document.status = "processing"
        db.commit()

        try:
            segments = extract_segments(document.file_path, document.file_type)
            chunks = chunk_segments(segments)
            if not chunks:
                raise ValueError("No extractable text was found in this document.")

            embeddings = embed_texts([c.text for c in chunks], task_type="RETRIEVAL_DOCUMENT")

            for index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                metadata = {"char_start": chunk.char_start, "char_end": chunk.char_end}
                if chunk.page_number is not None:
                    metadata["page_number"] = chunk.page_number
                if chunk.section_heading is not None:
                    metadata["section_heading"] = chunk.section_heading

                row = KnowledgeChunk(
                    document_id=document.id,
                    chunk_index=index,
                    text=chunk.text,
                    chunk_metadata_json=json.dumps(metadata),
                )
                db.add(row)
                db.flush()  # assign row.id before it's used as the vector store key
                row.embedding_id = vector_store.add_chunk(row.id, embedding, document.id)

            document.status = "indexed"
            document.indexed_at = datetime.utcnow()
            document.error_message = None
            document.chunk_count = len(chunks)
            db.commit()

        except Exception as exc:  # noqa: BLE001 — any real failure becomes an honest failed status
            db.rollback()
            document = db.get(KnowledgeDocument, document_id)
            if document is not None:
                document.status = "failed"
                document.error_message = str(exc)[:500]
                db.commit()
    finally:
        db.close()


def reprocess_document(db: Session, document: KnowledgeDocument) -> None:
    """[RAG] #241 — re-indexing workflow: drops this document's existing
    chunks (SQL + vector store) and resets it to "uploaded" so a fresh
    `process_document_task()` run rebuilds them from scratch. Used when
    the chunking/embedding pipeline changes, or to recover a "failed"
    document after fixing whatever made it fail (e.g. re-uploading isn't
    needed — the same source file on disk is re-extracted).
    """
    vector_store.delete_document(document.id)
    for chunk in list(document.chunks):
        db.delete(chunk)
    document.status = "uploaded"
    document.indexed_at = None
    document.error_message = None
    document.chunk_count = 0
    db.commit()


def delete_document(db: Session, document: KnowledgeDocument) -> None:
    """[RAG] #230 — document lifecycle management (delete). Removes the
    vector store entries, the SQL row (cascades to its chunks — see
    `KnowledgeDocument.chunks`'s cascade config), and the raw file on
    disk, in that order, so a partial failure never leaves an orphaned
    vector pointing at a SQL row that no longer exists.
    """
    vector_store.delete_document(document.id)
    file_path = document.file_path
    db.delete(document)
    db.commit()
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass  # the DB record is already gone; a leftover file is harmless


def search_knowledge(db: Session, query_text: str, top_k: int = 5) -> list[dict]:
    """[RAG] #248-#252 — real semantic search: embeds ``query_text`` as
    a RETRIEVAL_QUERY vector, asks the vector store for the closest
    chunks, and joins each hit back to its real SQL `KnowledgeChunk`/
    parent `KnowledgeDocument` row (never trusting Chroma's own copy of
    the text/title as authoritative — see vector_store.py's docstring).

    Only chunks belonging to a document whose current `status ==
    "indexed"` are returned — a document mid-reprocessing or already
    deleted can still have a stale vector-store entry for a moment (the
    vector store and the SQL row are updated in two separate steps, not
    one transaction), and this filter is what keeps a stale hit from
    ever reaching a citation.

    Returns ``[]`` for a blank query, or once nothing has ever been
    indexed — an honest empty result, not an error. Raises
    ``EmbeddingError`` (propagated, not swallowed) if the embedding call
    itself fails — the caller (the `search_knowledge` tool wrapper, or
    the Knowledge Center's search endpoint) decides how to degrade,
    matching how every other real external-call failure in this
    codebase is handled explicitly at its own call site rather than
    silently absorbed here.
    """
    if not query_text.strip():
        return []

    started = time.monotonic()
    query_embedding = embed_text(query_text, task_type="RETRIEVAL_QUERY")
    hits = vector_store.query(query_embedding, n_results=top_k)

    results: list[dict] = []
    for chunk_id, score in hits:
        chunk = db.get(KnowledgeChunk, chunk_id)
        if chunk is None or chunk.document is None or chunk.document.status != "indexed":
            continue
        results.append(
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "document_title": chunk.document.title,
                "text": chunk.text,
                "score": score,
            }
        )

    _log_search(db, query_text, results, duration_ms=int((time.monotonic() - started) * 1000))
    return results


def _log_search(db: Session, query_text: str, results: list[dict], *, duration_ms: int) -> None:
    """[RAG] Phase 10 (#275-#279) — one real row per completed search, the
    data source for every retrieval-analytics metric. Logged here, the
    one real call site, so both the `search_knowledge` specialist tool
    and the Knowledge Center's own search endpoint are captured
    identically. Best-effort: a logging failure must never break a
    search result the caller is actively waiting on.
    """
    try:
        top = results[0] if results else None
        db.add(
            KnowledgeSearchLog(
                query=query_text[:500],
                result_count=len(results),
                top_document_id=top["document_id"] if top else None,
                top_score=top["score"] if top else None,
                duration_ms=duration_ms,
            )
        )
        db.commit()
    except Exception:  # noqa: BLE001 — analytics logging must never break a real search
        db.rollback()
