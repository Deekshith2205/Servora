from pydantic import BaseModel


class ChatRequest(BaseModel):
    customer_id: int
    message: str


class TraceStepOut(BaseModel):
    agent: str
    output: str


class HandoffPacketOut(BaseModel):
    """Mirrors app.agents.escalation.HandoffPacket. Issue #13: exposes it
    through the API so the frontend can show a real handoff summary
    instead of the generic "a human agent will follow up" text."""

    situation: str
    attempted_fixes: list[str]
    root_cause_hypothesis: str
    recommended_action: str
    urgency: int


class ChatResponse(BaseModel):
    reply: str
    status: str
    trace: list[TraceStepOut]
    handoff_packet: HandoffPacketOut | None = None


class TicketOut(BaseModel):
    id: int
    customer_id: int
    category: str
    subject: str
    message: str
    sentiment: str
    urgency: int
    status: str

    class Config:
        from_attributes = True


class EscalationDetailOut(BaseModel):
    """Issue #14: full detail for one escalated ticket — the trace and
    handoff packet are parsed out of Ticket.trace_json /
    handoff_packet_json, which are only ever populated for tickets
    created by a real /api/chat escalation (see orchestrator.py's
    _create_escalation_ticket()). Both are None for the seeded demo
    tickets, which never went through the pipeline."""

    id: int
    customer_id: int
    category: str
    subject: str
    message: str
    sentiment: str
    urgency: int
    status: str
    trace: list[TraceStepOut] | None = None
    handoff_packet: HandoffPacketOut | None = None


class ResolveTicketRequest(BaseModel):
    """Issue #17. `resolution_notes` is free text from the human agent —
    the Learning Agent needs to know HOW it was fixed, not just what the
    problem was, to draft a useful KB article."""

    resolution_notes: str = ""


class KBArticleDraftOut(BaseModel):
    """Mirrors app.agents.learning.DraftKBArticle."""

    should_add: bool
    title: str
    body: str
    tags: list[str]


class ResolveTicketResponse(BaseModel):
    ticket: TicketOut
    kb_suggestion: KBArticleDraftOut | None = None


class ApproveKBArticleRequest(BaseModel):
    title: str
    body: str
    tags: list[str] = []


class KBArticleOut(BaseModel):
    id: int
    title: str
    body: str
    tags: str  # comma-separated, matches the KBArticle model's storage shape

    class Config:
        from_attributes = True
