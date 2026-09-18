"""[RAG] issue #225 — Knowledge Center API. Phase 2 (#231-#236 upload/
ingestion), Phase 5 (#248-#252 retrieval), Phase 9 (the endpoints the
frontend Knowledge Center page — #268-#274 — calls).

Upload is a two-step, honest-status flow, matching this codebase's own
"background task after the response is already sent" convention
(app/services/knowledge_retrieval.py's own docstring): POST returns
immediately once the file is validated and saved (status="uploaded"),
then a FastAPI BackgroundTask runs the real extract/chunk/embed/store
pipeline. The frontend polls GET .../documents or .../documents/{id} to
watch status reach "indexed" (or "failed", with a real error_message) —
never a fabricated "done" the instant the request returns.

Read access (list/detail/search) is gated by "view_knowledge_base"
(Support Agent, Manager, Administrator); write access (upload/delete/
reprocess) reuses "manage_knowledge_base" (Administrator-only, the same
permission issue #203 already established for KB article approval) —
uploading a real policy document into what specialists ground answers in
is a content-publishing action, same trust level as approving a KB
article.
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile

from sqlalchemy.orm import Session

from app.api.schemas import (
    KnowledgeChunkOut,
    KnowledgeDocumentDetailOut,
    KnowledgeDocumentOut,
    KnowledgeDocumentUploadOut,
    KnowledgeSearchResultOut,
)
from app.auth.dependency import require_permission
from app.db.database import get_db
from app.db.models import KnowledgeDocument
from app.services import knowledge_retrieval
from app.services.document_processing import UnsupportedFileTypeError
from app.services.embeddings import EmbeddingError
from app.services.knowledge_retrieval import EmptyFileError, FileTooLargeError

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _to_document_out(document: KnowledgeDocument) -> KnowledgeDocumentOut:
    """Explicit construction, never bare `from_attributes` on the ORM
    object — `uploaded_at`/`indexed_at` are real `datetime` columns but
    the schema declares plain `str` fields (matching this codebase's own
    convention elsewhere, e.g. PaymentRecordOut/TicketRecordOut), and
    Pydantic v2 does NOT auto-coerce a `datetime` into a `str` field via
    `from_attributes` — it raises a real validation error. Confirmed
    directly before writing this rather than assumed."""
    return KnowledgeDocumentOut(
        id=document.id,
        title=document.title,
        filename=document.filename,
        file_type=document.file_type,
        file_size_bytes=document.file_size_bytes,
        status=document.status,
        uploaded_at=document.uploaded_at.isoformat(),
        indexed_at=document.indexed_at.isoformat() if document.indexed_at else None,
        error_message=document.error_message,
        chunk_count=document.chunk_count,
    )


def _to_chunk_out(chunk) -> KnowledgeChunkOut:
    return KnowledgeChunkOut(
        id=chunk.id,
        document_id=chunk.document_id,
        chunk_index=chunk.chunk_index,
        text=chunk.text,
        chunk_metadata=chunk.chunk_metadata,
        created_at=chunk.created_at.isoformat(),
    )


@router.get("/documents", response_model=list[KnowledgeDocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    _actor=Depends(require_permission("view_knowledge_base")),
) -> list[KnowledgeDocumentOut]:
    """[RAG] #270 — the document management table's data source. Newest
    first, matching every other list endpoint in this codebase."""
    documents = db.query(KnowledgeDocument).order_by(KnowledgeDocument.uploaded_at.desc()).all()
    return [_to_document_out(d) for d in documents]


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentDetailOut)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    _actor=Depends(require_permission("view_knowledge_base")),
) -> KnowledgeDocumentDetailOut:
    """[RAG] #274 — document detail view, including every real chunk."""
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Knowledge document {document_id} not found")
    base = _to_document_out(document)
    return KnowledgeDocumentDetailOut(
        **base.model_dump(),
        chunks=[_to_chunk_out(c) for c in document.chunks],
    )


@router.post("/documents", response_model=KnowledgeDocumentUploadOut)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    title: str = Query(default=""),
    db: Session = Depends(get_db),
    _actor=Depends(require_permission("manage_knowledge_base")),
) -> KnowledgeDocumentUploadOut:
    """[RAG] #231-#236 — validates and persists the upload, then schedules
    the real extract/chunk/embed pipeline as a background task. `title`
    is an optional query param (a plain file upload has no natural place
    for a second text field without a second multipart part) — falls back
    to the filename when blank, matching `create_document()`'s own
    behavior.
    """
    content = await file.read()
    file_type = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    try:
        document = knowledge_retrieval.create_document(
            db,
            title=title or (file.filename or "untitled"),
            filename=file.filename or "untitled",
            file_type=file_type,
            content=content,
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except EmptyFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    background_tasks.add_task(knowledge_retrieval.process_document_task, document.id)
    return KnowledgeDocumentUploadOut(
        id=document.id,
        title=document.title,
        filename=document.filename,
        file_type=document.file_type,
        status=document.status,
    )


@router.post("/documents/{document_id}/reprocess", response_model=KnowledgeDocumentOut)
def reprocess_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _actor=Depends(require_permission("manage_knowledge_base")),
) -> KnowledgeDocumentOut:
    """[RAG] #241 — re-indexing workflow, exposed over the API (e.g. to
    recover a "failed" document, or rebuild after a pipeline change)."""
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Knowledge document {document_id} not found")
    knowledge_retrieval.reprocess_document(db, document)
    background_tasks.add_task(knowledge_retrieval.process_document_task, document.id)
    return _to_document_out(document)


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    _actor=Depends(require_permission("manage_knowledge_base")),
) -> dict:
    """[RAG] #230/#273 — real deletion: the SQL row (cascades to chunks),
    the vector store entries, and the raw file on disk."""
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=f"Knowledge document {document_id} not found")
    knowledge_retrieval.delete_document(db, document)
    return {"status": "deleted", "id": document_id}


@router.get("/search", response_model=list[KnowledgeSearchResultOut])
def search(
    q: str = Query(..., min_length=1),
    top_k: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    _actor=Depends(require_permission("view_knowledge_base")),
) -> list[dict]:
    """[RAG] #248-#252/#272 — the Knowledge Center's own search interface,
    and a convenient way to verify retrieval quality directly without
    going through a full chat turn. Raises a real 502 on an embedding
    failure (no/invalid Google API key, rate limit) — this endpoint's
    whole point IS the search result, so there is no best-effort degrade
    path the way a specialist tool call has."""
    try:
        return knowledge_retrieval.search_knowledge(db, q, top_k=top_k)
    except EmbeddingError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
