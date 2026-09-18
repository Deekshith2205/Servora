from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    customer_id: int
    message: str
    # [SWARM] issue #79: optional, client-generated (a UUID) — when
    # present, the frontend has already opened
    # GET /api/investigations/stream/{stream_key} and wants real-time
    # events published there as this pipeline run actually executes.
    # None (the default) reproduces the exact previous behavior.
    stream_key: str | None = None
    # [Omnichannel] issue #133: which Channel.key this message came in
    # on (see app/db/models.py::Channel). "live_chat" (the default)
    # reproduces the exact previous behavior for every existing caller —
    # this is the only channel that actually sends real traffic through
    # this endpoint today; other channels route through it via a future
    # normalization layer (issue #142), not directly from a browser.
    channel: str = "live_chat"


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
    # [Future Scope #302 audit] a real, previously-flagged bug: this
    # field was missing entirely, so every TicketOut-shaped response
    # (GET /api/tickets/mine, /api/escalations, /api/tickets/resolved)
    # silently dropped `created_at` — the frontend's own
    # `new Date(ticket.created_at)` then rendered as "Invalid Date"
    # (see CustomerResolutionHistory.jsx, flagged in CLAUDE.md's
    # 2026-09-17 entry, never fixed until now). A plain `datetime` field
    # (not `str`) — Pydantic v2's `from_attributes` correctly serializes
    # a real `datetime.datetime` to an ISO8601 JSON string on its own;
    # confirmed directly before relying on it, since a same-shaped `str`
    # field does NOT auto-coerce (see KnowledgeDocumentOut's own history
    # for where that assumption broke).
    created_at: datetime

    class Config:
        from_attributes = True


class CustomerProfileOut(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    tier: str
    # [Explainability #123]: additive — every existing caller of
    # GET /api/records/customers/{id} (EvidenceExplorer.jsx included)
    # keeps working unchanged; the new drill-down drawer's
    # SourceRecordViewer is just the first caller to actually render
    # these. `previous_tickets_count` is a real count of this customer's
    # own ticket history. `risk_level` reuses analytics.py's existing
    # churn-risk thresholds (CHURN_MEDIUM_THRESHOLD/CHURN_HIGH_THRESHOLD)
    # rather than inventing a second set of numbers — see
    # app/api/records.py::get_customer() for the computation. Neither is
    # a stored column; both are computed at read time from the same
    # Ticket rows /api/analytics already aggregates. There is no
    # "Account Status" concept anywhere in this schema — deliberately not
    # fabricated here just to match an example UI mockup.
    previous_tickets_count: int = 0
    # None when there's nothing concerning to flag (not a fabricated
    # "low") — only "medium"/"high" are ever set. See
    # app/api/records.py::_risk_level() for the exact thresholds.
    risk_level: str | None = None
    channels_used: list[str] = Field(default_factory=list)
    conversation_history: list["CustomerHistoryTicketOut"] = Field(default_factory=list)
    # Customer Context panel fields (Customer Chat's right-side panel) —
    # additive, computed at read time from Order/Payment rows this
    # customer actually owns, never fabricated. `customer_since` has no
    # backing `Customer.created_at` column (see models.py::Payment's own
    # docstring for why this repo avoids ALTERing an existing table) —
    # it's the earliest known Order/Payment timestamp instead, a
    # documented proxy, not a stored fact.
    customer_since: str | None = None
    # This app has no account-suspension concept at all — "active" is a
    # real, honest constant here, not a fabricated status field.
    account_status: str = "active"
    total_orders: int = 0
    last_order: dict | None = None
    payment_method: str | None = None
    recent_refund_requests: list[dict] = Field(default_factory=list)


class CustomerHistoryTicketOut(BaseModel):
    id: int
    subject: str
    category: str
    status: str
    sentiment: str
    urgency: int
    created_at: str
    channel: str = "live_chat"

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

class EscalationQueueOut(BaseModel):
    value: list[TicketOut]
    today_resolved_count: int

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
    # [Future Scope #302 audit] same missing-field bug as TicketOut's own
    # `created_at` (see that field's comment) — CustomerDashboard.jsx's
    # `new Date(notif.created_at)` was silently rendering "Invalid Date"
    # for every notification.
    created_at: datetime

    class Config:
        from_attributes = True


class UpdateBookingResponse(BaseModel):
    """Mirrors issue #17's ResolveTicketResponse (ticket + kb_suggestion)
    pattern: the booking, plus the notification this edit produced (None
    when the PATCH changed nothing, so nothing was sent)."""

    booking: BookingDetailOut
    notification: NotificationOut | None = None


class AlternativeOut(BaseModel):
    """One rejected alternative from app.agents.planner.Alternative —
    [EXPLAIN] issue #89."""

    action: str
    rejected_because: str


class EvidenceRefOut(BaseModel):
    """One structured, id-addressable evidence reference — [EXPLAIN]
    issue #91. `type` is one of: order | customer | ticket | kb_article."""

    type: str
    ref_id: int
    label: str


class CriticReviewOut(BaseModel):
    """[CRITIC] issue #111. Mirrors app.agents.critic.CriticReview — only
    populated on the critic's own InvestigationStep (agent_name ==
    "critic"), `None` everywhere else."""

    agrees: bool
    confidence: float
    alternative_hypothesis: str | None = None
    reasoning: str


class InvestigationStepOut(BaseModel):
    """One row from app.db.models.InvestigationStep — [FEATURE]
    Investigation Board. `started_at`/`reasoning`/`used_tools`/
    `alternatives_considered`/`evidence_refs` added by [SWARM] #77 and
    [EXPLAIN] #89/#91 — all optional/default-empty so older rows (written
    before these columns existed) still serialize cleanly. `critic_review`
    added by [CRITIC] #108/#111, same convention."""

    step_number: int
    timestamp: str
    started_at: str | None = None
    agent_name: str
    action: str
    status: str
    reasoning: str | None = None
    evidence: list[str]
    evidence_refs: list[EvidenceRefOut] = []
    used_tools: list[str] = []
    alternatives_considered: list[AlternativeOut] = []
    critic_review: CriticReviewOut | None = None
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


class GraphNodeOut(BaseModel):
    """[SWARM] issue #80. One InvestigationStep, shaped for a node/edge
    render rather than a flat list."""

    step_number: int
    agent_name: str
    status: str
    confidence: float | None = None
    duration_ms: int


class GraphEdgeOut(BaseModel):
    """[SWARM] issue #80. Today's pipeline is strictly sequential per run
    (no fan-out/fan-in yet — see issue #78 for the future, explicitly-
    modeled version of this), so edges are correctly derivable from step
    order alone: step N -> step N+1. Kept as its own type (not just
    "the next step_number") so the frontend graph renderer doesn't need
    to know that today's rule is "sequential" — a future #78 could repoint
    edges to real fan-in/fan-out without changing this shape at all."""

    from_step: int
    to_step: int


class InvestigationGraphOut(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]


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
    # [SWARM] issue #80 — additive.
    graph: InvestigationGraphOut
    # [Omnichannel] issue #134 — additive. `None` for every Live Chat
    # investigation (the common case today) and every row written before
    # this column existed; a real dict (e.g. a WhatsApp
    # `external_conversation_id`) once a channel adapter (issue #142)
    # supplies one.
    channel_metadata: dict | None = None
    # [Omnichannel] issue #146 — additive. `Investigation.channel_key` has
    # existed since issue #133, but this read API never actually exposed
    # it — every row, old and new, has a real value ("live_chat" for
    # everything that predates the Channel Foundation work), never null.
    channel: str = "live_chat"


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
    # [Omnichannel] issue #146 — additive, same convention as
    # InvestigationOut.channel/channel_metadata above.
    channel: str = "live_chat"
    channel_metadata: dict | None = None


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


class ConfidenceBreakdownOut(BaseModel):
    """[EXPLAIN] issue #90. One agent's own confidence, WITHIN one
    investigation — distinct from AgentPerformanceOut's avg_confidence,
    which is a cross-investigation aggregate."""

    agent_name: str
    confidence: float


class ConfidenceOut(BaseModel):
    """GET /api/investigations/{id}/confidence — [EXPLAIN] issue #92."""

    overall: float | None = None
    by_agent: list[ConfidenceBreakdownOut] = []


class EvidenceOut(BaseModel):
    """GET /api/investigations/{id}/evidence — [EXPLAIN] issue #92.
    `evidence`/`policy_references` are disjoint views of the same
    underlying evidence_refs — `policy_references` is exactly the
    `type == "kb_article"` subset."""

    evidence: list[str] = []
    evidence_refs: list[EvidenceRefOut] = []
    policy_references: list[EvidenceRefOut] = []


class OrderRecordOut(BaseModel):
    """[EXPLAIN] issue #95: the inline preview an Evidence Explorer "order"
    reference opens — just enough fields to explain the evidence, not a
    full order-management view."""

    id: int
    customer_id: int
    product: str
    amount: float
    status: str
    payment_status: str
    failure_reason: str | None = None
    duplicate_of: int | None = None

    class Config:
        from_attributes = True


class PaymentRecordOut(BaseModel):
    """The inline preview a "payment" evidence reference opens — mirrors
    OrderRecordOut's role, for the Payment table added alongside the
    e-commerce demo scenarios (see models.py::Payment)."""

    id: int
    customer_id: int
    order_id: int | None = None
    amount: float
    method: str
    description: str
    status: str
    payment_type: str
    duplicate_of: int | None = None
    charged_at: str


class TicketRecordOut(BaseModel):
    """[EXPLAIN] issue #95: the inline preview a "ticket" evidence
    reference opens."""

    id: int
    customer_id: int
    category: str
    subject: str
    status: str
    sentiment: str
    urgency: int
    created_at: str


class ExplanationOut(BaseModel):
    """GET /api/investigations/{id}/explanation — [EXPLAIN] issue #92.
    The Explainable AI Panel's single source of data. `decision_rationale`
    is composed deterministically from existing fields (root_cause +
    resolution, or the HandoffPacket for an escalation) — no extra LLM
    call, per that issue's explicit design choice."""

    investigation_id: int
    status: str
    channel: str = "live_chat"
    confidence: ConfidenceOut
    evidence: list[str] = []
    evidence_refs: list[EvidenceRefOut] = []
    policy_references: list[EvidenceRefOut] = []
    # [EXPLAIN] issue #96: which action was actually taken — None only if
    # somehow no planner step was recorded at all. Kept separate from
    # `alternatives_considered` (which never includes this value) so a
    # frontend can render the two visually distinct, per that issue's own
    # acceptance criteria.
    chosen_action: str | None = None
    alternatives_considered: list[AlternativeOut] = []
    agents_consulted: list[InvestigationAgentSummaryOut] = []
    decision_rationale: str


class ToolExecutionOut(BaseModel):
    """[Explainability #121/#123]: one tool that ran as part of the step an
    evidence item came from. `duration_ms`/`records_returned` are
    STEP-level values attributed to each tool the step used — this system
    records timing and evidence-ref counts per InvestigationStep, not per
    individual tool call within a step (no such column exists), so a step
    that called two tools shows the same duration/count on both rather
    than a fabricated per-tool split. Documented approximation, same
    spirit as verification.py's own documented one."""

    tool_name: str
    duration_ms: int
    records_returned: int


class EvidenceConfidenceBreakdownOut(BaseModel):
    """[Explainability #122/#123]: three sub-scores explaining *why* one
    evidence item carries the confidence it does — deterministic, derived
    from real existing signals, no new LLM call. See
    app/api/explanations.py::_evidence_confidence_breakdown() for the
    exact formulas and the reasoning behind each one."""

    evidence_quality: float
    data_freshness: float
    source_reliability: float


class EvidenceDetailOut(BaseModel):
    """GET /api/investigations/{id}/evidence/{evidenceId} —
    [Explainability #123]. `evidenceId` addresses one entry of a step's
    `evidence_refs` list as "{step_number}:{index}" — evidence refs
    aren't individually-addressable DB rows today, so this composite key
    avoids a schema change entirely. Deliberately does NOT re-embed the
    full source record (order/customer/ticket/kb_article) — that's
    already served by /api/records/... and /api/kb-articles/{id}; the
    frontend fetches it separately via those same existing endpoints
    (see EvidenceExplorer.jsx), keeping this response focused on what
    only THIS endpoint can provide."""

    investigation_id: int
    evidence_id: str
    step_number: int
    title: str
    agent_name: str
    timestamp: str
    confidence: float | None = None
    evidence_ref: EvidenceRefOut
    reasoning: str
    tools: list[ToolExecutionOut] = []
    confidence_breakdown: EvidenceConfidenceBreakdownOut
    impact: str


# --------------------------------------------------------------------- #
# Omnichannel Inbox (Phase 2)
# --------------------------------------------------------------------- #

class CompactCustomerOut(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True


class InboxItemOut(BaseModel):
    """GET /api/inbox — one row per Ticket, forming the Unified Inbox list."""
    id: int
    customer: CompactCustomerOut
    channel_key: str
    subject: str
    preview: str
    status: str
    updated_at: str
    has_investigation: bool


class InboxDetailOut(BaseModel):
    """GET /api/inbox/{ticket_id} — the full conversation detail for the Inbox."""
    id: int
    customer: CompactCustomerOut
    channel_key: str
    subject: str
    message: str
    status: str
    updated_at: str
    investigation_id: int | None = None

# [Omnichannel] Channel Foundation — issue #135
# --------------------------------------------------------------------- #


class ChannelOut(BaseModel):
    """One row from app.db.models.Channel — see that model's docstring."""

    id: int
    key: str
    display_name: str
    status: str  # active | inactive | not_configured
    config: dict = {}


class UpdateChannelStatusRequest(BaseModel):
    status: str  # active | inactive | not_configured
# --------------------------------------------------------------------- #
# Shopify integration — Settings -> Integrations
# --------------------------------------------------------------------- #


class ShopifyConnectRequest(BaseModel):
    store_url: str
    access_token: str


class ShopifyStatusOut(BaseModel):
    """GET /api/integrations/shopify/status. Deliberately never includes
    `access_token` — this is the ONLY read path a frontend has into the
    integration row, and the raw credential must never round-trip back
    to the browser once saved (see ShopifyIntegration's own docstring on
    why the token is stored in plain text server-side in the first
    place). `store_url` alone is not a secret — it's a public storefront
    hostname."""

    connected: bool
    store_url: str | None = None
    status: str  # connected | disconnected | error | never_connected
    last_sync_at: str | None = None
    last_error: str | None = None
    connected_orders_count: int | None = None


class ShopifyOrderRecordOut(BaseModel):
    """[Explainability]: the inline preview a `shopify_order` evidence
    reference opens — mirrors OrderRecordOut's role for Servora's own
    orders, just backed by a live Shopify API call instead of a local
    DB row."""

    id: int
    order_number: str | None = None
    email: str | None = None
    total_price: str | None = None
    financial_status: str | None = None
    fulfillment_status: str | None = None
    created_at: str | None = None


class ShopifyCustomerRecordOut(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    orders_count: int | None = None
    total_spent: str | None = None


# --------------------------------------------------------------------- #
# [RBAC] Role-Based Access Control — issues #171-#223
# --------------------------------------------------------------------- #


class CurrentActorOut(BaseModel):
    """GET /api/auth/me — mirrors app.auth.dependency.CurrentActor.
    `role=None` is the real, honest "not resolved" state (missing/
    invalid identity headers), never a fabricated default role."""

    role: str | None = None
    customer_id: int | None = None
    user_id: int | None = None
    name: str | None = None


class UserOut(BaseModel):
    """One row from app.db.models.User — a seeded/administrator-created
    staff identity. Never carries a credential (there isn't one)."""

    id: int
    name: str
    email: str
    role: str

    class Config:
        from_attributes = True


class CreateUserRequest(BaseModel):
    name: str
    email: str
    role: str
    # Real auth: an Administrator sets a new staff member's initial
    # password directly (there's no public staff sign-up — see
    # app/api/auth.py's own module docstring for why that split exists).
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    """Public self-registration — customers only, see app/api/auth.py."""

    name: str
    email: str
    password: str = Field(min_length=8)


class GoogleSignInRequest(BaseModel):
    """The ID token Google Identity Services' JS client returns after a
    successful "Sign in with Google" — a signed JWT, verified server-side
    against Google's own public keys in app/api/auth.py::google_sign_in().
    Never a password, never an authorization code."""

    credential: str


class AuthTokenOut(BaseModel):
    """POST /api/auth/login|register|me-after-register response — enough
    for the frontend to both store the session token and immediately
    know who it belongs to, without a second round-trip to /auth/me."""

    token: str
    role: str
    user_id: int | None = None
    customer_id: int | None = None
    name: str


class UpdateUserRequest(BaseModel):
    """[RBAC] issue #200: PATCH semantics, all fields optional — only
    what an Administrator actually changed gets sent."""

    name: str | None = None
    role: str | None = None


class SystemSettingOut(BaseModel):
    key: str
    value: str

    class Config:
        from_attributes = True


class UpdateSystemSettingRequest(BaseModel):
    value: str


class TeamActivityEntryOut(BaseModel):
    """[RBAC] issue #197 — one seeded staff member's real, current open/
    escalated ticket count, matched to them by `Ticket.assigned_to`
    (a free-text name match, not a FK — see that issue's own honest
    scope note)."""

    user_id: int
    name: str
    role: str
    open_ticket_count: int
    escalated_ticket_count: int
