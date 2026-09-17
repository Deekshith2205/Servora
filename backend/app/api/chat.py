from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import ChatRequest, ChatResponse
from app.auth.dependency import CurrentActor, get_current_actor
from app.auth.roles import CUSTOMER
from app.db.database import get_db
from app.llm import LLMError
from app.orchestrator import handle_message
from app.rate_limit import rate_limit

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(rate_limit)])
def chat(
    payload: ChatRequest, db: Session = Depends(get_db), actor: CurrentActor = Depends(get_current_actor)
) -> ChatResponse:
    # [RBAC] issue #177: a real DATA-LEVEL check, not just a permission
    # check — only enforced when a real Customer identity was actually
    # asserted (via the Role Switcher's headers, issue #206, Track B).
    # An anonymous caller (no identity headers at all — the ONLY way
    # this endpoint has ever been called before this issue, since
    # Track B's header-sending Role Switcher is a separate, not-yet-
    # merged piece of work) is left completely unaffected, so this
    # stays additive rather than a breaking change to the live app the
    # moment this PR alone lands. A caller that DOES assert a Customer
    # identity, but for a DIFFERENT customer_id than the payload claims,
    # gets a real 403 — the actual enforcement this issue's own
    # acceptance criteria names.
    if actor.role == CUSTOMER and actor.customer_id is not None and actor.customer_id != payload.customer_id:
        raise HTTPException(status_code=403, detail="You do not have permission to perform this action.")

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
