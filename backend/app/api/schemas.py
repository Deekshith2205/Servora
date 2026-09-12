from pydantic import BaseModel


class ChatRequest(BaseModel):
    customer_id: int
    message: str


class TraceStepOut(BaseModel):
    agent: str
    output: str
    confidence: float | None = None
    root_cause: str | None = None
    resolution: str | None = None


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
    # Found while wiring up [FEATURE] Investigation Board: orchestrator.py's
    # ChatResult has carried a real ticket_id since issue #14, but it was
    # never actually included in this response — the frontend had no way
    # to link a just-completed conversation to its ticket (or now, its
    # Investigation) without a separate, fragile lookup. Additive/optional
    # so no existing caller of /api/chat breaks.
    ticket_id: int | None = None


class TicketOut(BaseModel):
    id: int
    customer_id: int
    category: str
    subject: str
    message: str
    sentiment: str
    urgency: int
    status: str
    confidence: float | None = None
    assigned_to: str | None = None

    class Config:
        from_attributes = True


class CustomerProfileOut(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    tier: str


class CustomerHistoryTicketOut(BaseModel):
    id: int
    subject: str
    category: str
    status: str
    sentiment: str
    urgency: int
    created_at: str

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
    confidence: float | None = None
    assigned_to: str | None = None
    trace: list[TraceStepOut] | None = None
    handoff_packet: HandoffPacketOut | None = None
    customer: CustomerProfileOut | None = None
    customer_history: list[CustomerHistoryTicketOut] | None = None


class AssignTicketRequest(BaseModel):
    assigned_to: str | None


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


class BookingMessage(BaseModel):
    """One turn of the booking conversation. Issue #18: the caller (the
    frontend) accumulates and resends the FULL transcript each turn — see
    app/agents/booking.py's module docstring for why this agent is
    stateless server-side."""

    role: str  # "user" | "assistant"
    content: str


class BookingChatRequest(BaseModel):
    customer_id: int
    messages: list[BookingMessage]


class BookingOut(BaseModel):
    id: int
    customer_id: int
    room_type: str
    check_in: str
    check_out: str
    guests: int
    total_price: float
    status: str

    class Config:
        from_attributes = True


class BookingChatResponse(BaseModel):
    reply: str
    booking: BookingOut | None = None


class BookingEditLogEntry(BaseModel):
    """One entry from Booking.edit_log_json — issue #20. Values are always
    strings (the log itself doesn't care about the field's real type, only
    about rendering "changed from X to Y" — issue #21's notification diff
    consumes this directly)."""

    field: str
    old_value: str
    new_value: str
    at: str


class BookingDetailOut(BookingOut):
    edit_log: list[BookingEditLogEntry] = []


class UpdateBookingRequest(BaseModel):
    """Issue #20: all fields optional — PATCH semantics, only the fields the
    staff member actually changed should be sent (and therefore logged)."""

    room_type: str | None = None
    check_in: str | None = None
    check_out: str | None = None
    guests: int | None = None
    total_price: float | None = None


class NotificationOut(BaseModel):
    """Issue #21 — see app/services/notifications.py for why this is a
    recorded row rather than a real email/SMS send."""

    id: int
    customer_id: int
    subject: str
    body: str

    class Config:
        from_attributes = True


class UpdateBookingResponse(BaseModel):
    """Mirrors issue #17's ResolveTicketResponse (ticket + kb_suggestion)
    pattern: the booking, plus the notification this edit produced (None
    when the PATCH changed nothing, so nothing was sent)."""

    booking: BookingDetailOut
    notification: NotificationOut | None = None


class InvestigationStepOut(BaseModel):
    """One row from app.db.models.InvestigationStep — [FEATURE]
    Investigation Board."""

    step_number: int
    timestamp: str
    agent_name: str
    action: str
    status: str
    evidence: list[str]
    duration_ms: int
    confidence: float | None = None


class InvestigationAgentSummaryOut(BaseModel):
    """Per-agent rollup WITHIN one investigation (how many of its steps
    that agent ran, total/avg time) — the per-investigation "agents"
    array the issue's example JSON asks for. See
    GET /api/investigations/metrics/agents for the cross-investigation
    version that actually makes "Agent Performance Metrics" meaningful."""

    agent_name: str
    steps: int
    total_duration_ms: int


class InvestigationOut(BaseModel):
    id: int
    ticket_id: int
    customer_id: int
    started_at: str
    completed_at: str | None = None
    confidence: float | None = None
    root_cause: str | None = None
    resolution: str | None = None
    status: str
    timeline: list[InvestigationStepOut]
    agents: list[InvestigationAgentSummaryOut]
    evidence: list[str]


class InvestigationListItemOut(BaseModel):
    """Summary row for the Investigation Board's browse list — enough to
    render a card without fetching every full investigation."""

    id: int
    ticket_id: int
    customer_id: int
    status: str
    root_cause: str | None = None
    confidence: float | None = None
    started_at: str


class AgentPerformanceOut(BaseModel):
    """One agent's aggregate stats ACROSS every investigation — a real
    SQL GROUP BY over InvestigationStep, not a per-investigation view.
    This is what makes "Agent Performance Metrics" a meaningful section
    rather than one data point per agent."""

    agent_name: str
    total_steps: int
    avg_duration_ms: float
    avg_confidence: float | None = None


class InvestigationMetricsOut(BaseModel):
    agents: list[AgentPerformanceOut]
