from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import ChatRequest, ChatResponse
from app.db.database import get_db
from app.orchestrator import handle_message

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    result = handle_message(db, payload.customer_id, payload.message)
    return ChatResponse(reply=result.reply, status=result.status, trace=[s.__dict__ for s in result.trace])
