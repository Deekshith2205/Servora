"""Booking conversation endpoint. Implements issue #18's API surface — see
app/agents/booking.py for the agent itself and its statelessness note.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.booking import run_booking_agent
from app.api.schemas import BookingChatRequest, BookingChatResponse
from app.db.database import get_db
from app.db.models import Customer
from app.llm import LLMError
from app.rate_limit import rate_limit

router = APIRouter(prefix="/api", tags=["booking"])


@router.post("/booking", response_model=BookingChatResponse, dependencies=[Depends(rate_limit)])
def booking_chat(payload: BookingChatRequest, db: Session = Depends(get_db)) -> BookingChatResponse:
    if db.get(Customer, payload.customer_id) is None:
        raise HTTPException(status_code=404, detail=f"Customer {payload.customer_id} not found")

    try:
        result = run_booking_agent(
            db,
            payload.customer_id,
            [{"role": m.role, "content": m.content} for m in payload.messages],
        )
    except LLMError as e:
        # Unlike issue #17's KB-drafting (best-effort, degrades silently),
        # a failure here IS the customer's whole request — there's nothing
        # sensible to degrade to. Raise it as a proper HTTPException (502)
        # instead of letting it propagate unhandled: an unhandled exception
        # bypasses CORSMiddleware and the browser only ever sees an opaque
        # "Failed to fetch" (the same class of bug fixed for one specific
        # exception type in issue #17 — see CLAUDE.md's still-open general
        # gap). HTTPException responses go through FastAPI's normal handler
        # chain, which DOES include CORS headers.
        raise HTTPException(status_code=502, detail=str(e)) from e

    return BookingChatResponse(reply=result.reply, booking=result.booking)
