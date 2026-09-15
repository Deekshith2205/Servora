from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import ChatRequest, ChatResponse
from app.db.database import get_db
from app.llm import LLMError
from app.orchestrator import handle_message

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    # Found live, with a real API key, once the account ran out of credit:
    # classify() has its own fallback for a failed LLM call (issue #57), but
    # plan()/the specialists/build_handoff_packet() do not, and this
    # endpoint never caught LLMError at all — any of those failing crashed
    # the whole request as an unhandled 500, which bypasses CORSMiddleware
    # (the browser sees a bare "Failed to fetch", not the actual reason).
    # Same fix already applied to issue #18's POST /api/booking — this
    # endpoint has no best-effort degrade path either (the reply IS the
    # response), so a clean HTTPException is the right shape here too.
    try:
        result = handle_message(
            db, payload.customer_id, payload.message, stream_key=payload.stream_key, channel=payload.channel
        )
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return ChatResponse(
        reply=result.reply,
        status=result.status,
        trace=[s.__dict__ for s in result.trace],
        # Issue #13: surface the real handoff packet when one exists (only
        # on the escalated path) instead of leaving the frontend with
        # nothing but the generic reply text.
        handoff_packet=asdict(result.handoff_packet) if result.handoff_packet else None,
        ticket_id=result.ticket_id,
    )
