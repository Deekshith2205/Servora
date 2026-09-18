"""[RAG] Phase 4: Embeddings & Vector Storage — #243 ChromaDB
integration, #245 vector storage layer.

ChromaDB, as named in the epic's own description — run embedded/local
(a single on-disk directory, no separate server process), matching this
project's SQLite-file/Neon-Postgres, zero-extra-infra demo philosophy
rather than standing up a second database service. `backend/chroma_data/`
is gitignored (see .gitignore's own [RAG] #225 comment) — same reasoning
as `*.db`: real local index data, not something to version.

This module owns ONLY the vector side (add/query/delete a chunk's
embedding in the `knowledge_chunks` collection). It never touches
`KnowledgeChunk`'s SQL row directly — `app/services/knowledge_retrieval.py`
is the one place that joins a vector-store hit back to the real SQL
`text`/`chunk_metadata` (see that module's docstring for why the SQL
row, not Chroma's own metadata, is authoritative for a chunk's content).
"""
from __future__ import annotations

import os

import chromadb

_COLLECTION_NAME = "knowledge_chunks"

_client: chromadb.ClientAPI | None = None


def _persist_dir() -> str:
    """Read lazily (not a module-level constant) so `CHROMA_PERSIST_DIR`
    can be overridden — same "must be set before first real use, not
    baked in at import time" convention `tests/conftest.py` already
    established for `DATABASE_URL`. Without this, running `pytest` would
    read/write the SAME on-disk `chroma_data/` directory a local dev
    server uses — the identical class of test-pollution bug already
    found and fixed twice in this codebase (the SQLite test DB, and
    LLM_PROVIDER), now closed proactively here instead of waiting to hit
    it live.
    """
    return os.environ.get("CHROMA_PERSIST_DIR", "chroma_data")


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=_persist_dir())
    return _client


def _get_collection():
    # Cosine distance — the standard metric for comparing two Gemini
    # embedding vectors (see app/services/embeddings.py); Chroma's
    # default (l2) is not the metric these embeddings are meant to be
    # compared under.
    return _get_client().get_or_create_collection(
        _COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )


def add_chunk(chunk_id: int, embedding: list[float], document_id: int) -> str:
    """Stores one chunk's embedding, keyed by a stable string id derived
    from the real `KnowledgeChunk.id` — this IS the value
    `KnowledgeChunk.embedding_id` is set to (see that model's own
    docstring for why: joining a vector-store hit back to the real SQL
    row is a plain lookup by this id, not a second metadata store).
    `document_id` is stored as Chroma metadata so a whole document's
    vectors can be deleted in one call (see `delete_document()`) without
    the caller needing to enumerate every chunk id first.
    """
    embedding_id = f"chunk-{chunk_id}"
    _get_collection().add(
        ids=[embedding_id],
        embeddings=[embedding],
        metadatas=[{"chunk_id": chunk_id, "document_id": document_id}],
    )
    return embedding_id


def query(embedding: list[float], n_results: int = 5) -> list[tuple[int, float]]:
    """Returns up to ``n_results`` ``(chunk_id, score)`` pairs, ranked
    highest-score-first. ``score`` is a real similarity in [0, 1]
    (``1 - cosine_distance`` — Chroma reports cosine DISTANCE, not
    similarity, under the `hnsw:space: cosine` config `_get_collection()`
    sets; this inverts it so a caller never has to know that
    Chroma-specific convention) — never a fabricated confidence number.
    Returns an empty list against an empty collection (a fresh install
    with nothing uploaded yet) rather than raising.
    """
    collection = _get_collection()
    if collection.count() == 0:
        return []
    n_results = min(n_results, collection.count())
    result = collection.query(query_embeddings=[embedding], n_results=n_results)
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    return [(m["chunk_id"], 1.0 - d) for m, d in zip(metadatas, distances)]


def delete_document(document_id: int) -> None:
    """Deletes every chunk vector belonging to one document — [RAG] #230
    (document lifecycle) calls this when a document (and its
    `KnowledgeChunk` rows, cascade-deleted on the SQL side) is removed,
    so a stale vector never survives its own source document."""
    _get_collection().delete(where={"document_id": document_id})


def reset_for_tests() -> None:
    """Test-only: drops and recreates the collection so each test run
    starts from a clean vector store, mirroring the isolated-DB pattern
    `tests/conftest.py` already establishes for the SQL side."""
    client = _get_client()
    try:
        client.delete_collection(_COLLECTION_NAME)
    except Exception:  # noqa: BLE001 — collection may not exist yet
        pass
