"""Mock data model for the demo.

Deliberately small — enough tables to make every agent (classifier, billing,
technical, order, account, booking) have something real to query instead of
hallucinating. Extend as issues need more fields, don't redesign the shape
without flagging it in #base-scaffold first since several agents will read
these directly.
"""
import json
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True)
    phone: Mapped[str] = mapped_column(String, default="")
    tier: Mapped[str] = mapped_column(String, default="standard")  # standard | vip

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    product: Mapped[str] = mapped_column(String)
    amount: Mapped[float] = mapped_column(Float)
    
    # Fulfillment state
    status: Mapped[str] = mapped_column(String, default="processing")  # processing|shipped|delivered|failed|cancelled|refunded
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    
    # Issue #59: Payment state
    payment_status: Mapped[str] = mapped_column(String, default="paid")  # paid|failed|refunded
    duplicate_of: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True, default=None)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer: Mapped["Customer"] = relationship(back_populates="orders")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    category: Mapped[str] = mapped_column(String, default="")  # billing|technical|order|account
    subject: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(String)
    sentiment: Mapped[str] = mapped_column(String, default="")  # positive|neutral|negative
    urgency: Mapped[int] = mapped_column(Integer, default=0)  # 1-10
    status: Mapped[str] = mapped_column(String, default="open")  # open|resolved|escalated
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    # [Omnichannel] issue #133: which Channel.key this conversation came in
    # on. Not a real FK (see Channel's own docstring for why) — nullable-
    # safe default of "live_chat" means every existing row created before
    # this column existed reads as a real, honest Live Chat conversation,
    # never a fabricated/blank value.
    channel_key: Mapped[str] = mapped_column(String, default="live_chat")

    # Issue #14: JSON-encoded snapshots of the reasoning trace and handoff
    # packet from the /api/chat call that created this ticket (only set on
    # tickets created by a real escalation — nullable so the seeded demo
    # tickets, which never went through the pipeline, are unaffected).
    trace_json: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    handoff_packet_json: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    assigned_to: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    customer: Mapped["Customer"] = relationship(back_populates="tickets")


class KBArticle(Base):
    __tablename__ = "kb_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)
    tags: Mapped[str] = mapped_column(String, default="")  # comma-separated


class Room(Base):
    """Backs the hotel-booking stretch feature — ignore until that issue is picked up."""

    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_type: Mapped[str] = mapped_column(String)  # standard|deluxe|suite
    price_per_night: Mapped[float] = mapped_column(Float)
    total_count: Mapped[int] = mapped_column(Integer)


class Booking(Base):
    """Backs the hotel-booking stretch feature. Issue #18 (Booking Agent)
    creates rows here at status="AI_DRAFTED"; issue #20 (staff review/edit)
    is what actually reads/writes `edit_log_json` and drives the rest of
    the state machine (see docs/ARCHITECTURE.md): every edit made once a
    booking exists is logged (old value -> new value), and issue #21
    consumes that log to tell the customer exactly what changed.
    """

    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    room_type: Mapped[str] = mapped_column(String)
    check_in: Mapped[str] = mapped_column(String)
    check_out: Mapped[str] = mapped_column(String)
    guests: Mapped[int] = mapped_column(Integer, default=1)
    total_price: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, default="AI_DRAFTED")  # AI_DRAFTED|STAFF_REVIEWED|CONFIRMED
    # Issue #20: JSON-encoded list of {field, old_value, new_value, at} —
    # every staff edit appended, oldest first. A flat log (not a richer
    # schema) since the only consumer (#21's notification diff) just needs
    # to render "field changed from X to Y".
    edit_log_json: Mapped[str] = mapped_column(String, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @property
    def edit_log(self) -> list[dict]:
        """Parsed view of `edit_log_json` — lets BookingDetailOut's Pydantic
        `from_attributes` mode read it like any other attribute instead of
        every caller having to `json.loads` it themselves."""
        return json.loads(self.edit_log_json) if self.edit_log_json else []


class CustomerMemory(Base):
    """Backs issue #11 (customer memory write/merge) — see app/agents/memory.py.

    One row per customer. `facts_json` is a JSON-encoded list of short,
    durable fact strings (preferences, exceptions granted, recurring
    patterns) — deliberately a flat list, not a rich schema, since the only
    operation that matters is a set-union merge.
    """

    __tablename__ = "customer_memory"

    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), primary_key=True)
    facts_json: Mapped[str] = mapped_column(String, default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Investigation(Base):
    """Backs the [FEATURE] "AI Investigation Board & Autonomous Reasoning
    Timeline" — a normalized, queryable record of one /api/chat pipeline
    run, alongside (not replacing) `Ticket.trace_json` — see
    `orchestrator.py::_persist_investigation()`.

    Why a separate table instead of just parsing `Ticket.trace_json`
    harder: the Investigation Board's "Agent Performance Metrics" section
    needs real cross-investigation aggregation (avg duration per agent,
    etc.) — a JSON blob per ticket can't be GROUP BY'd in SQL without
    deserializing every row first. `InvestigationStep` below is the
    normalized per-step data that makes that a real query instead of an
    in-Python scan of every ticket's trace_json.

    One row per ticket — `ticket_id` is unique. `status` mirrors the
    shape a genuinely async/streaming pipeline would have
    ("investigating" -> "root_cause_found" -> "resolved"/"escalated"),
    for API completeness and future use, but see the orchestrator's own
    note: today's /api/chat is fully synchronous, so a row is only ever
    written once already complete — "investigating" and
    "root_cause_found" are valid values this column supports, not states
    any current caller will actually observe mid-flight.
    """

    __tablename__ = "investigations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    root_cause: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    resolution: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    # investigating | root_cause_found | escalated | resolved
    status: Mapped[str] = mapped_column(String, default="investigating")

    # [Omnichannel] issue #133: same convention as Ticket.channel_key —
    # additive, defaults to "live_chat" so every pre-existing row (every
    # Investigation created before this column existed) reads as real
    # Live Chat history, not a fabricated value.
    channel_key: Mapped[str] = mapped_column(String, default="live_chat")

    # [Omnichannel] issue #134: small JSON object of channel-specific
    # detail beyond the channel key itself — e.g. a WhatsApp/Instagram/
    # Messenger `external_conversation_id`/`external_contact`, or an
    # email's `subject`. Nullable (not a default-empty-object) precisely
    # because most investigations (every Live Chat one, today) genuinely
    # have nothing here — see the `channel_metadata` property below,
    # same "None over a fabricated empty value" convention this column's
    # sibling `critic_review_json` already established.
    channel_metadata_json: Mapped[str | None] = mapped_column(String, nullable=True, default=None)

    steps: Mapped[list["InvestigationStep"]] = relationship(
        back_populates="investigation", order_by="InvestigationStep.step_number"
    )

    @property
    def channel_metadata(self) -> dict | None:
        return json.loads(self.channel_metadata_json) if self.channel_metadata_json else None


class InvestigationStep(Base):
    """One agent's turn within an `Investigation` — see that model's
    docstring. `evidence_json` is a JSON-encoded list of short,
    human-readable strings derived from REAL tool call results (see
    `specialists.py`'s evidence-capturing wrapper) — never placeholder
    text, even when a step made no tool calls (its evidence list is then
    just empty, not faked).

    Issues [SWARM] #77 and [EXPLAIN] #89/#91 add the columns below —
    all additive, all default to an empty/null "nothing recorded" value
    so no existing row or caller breaks:
      - `started_at`: real wall-clock start (added alongside the
        pre-existing `timestamp`, which is written at COMPLETION —
        `timestamp - started_at` should be ~= `duration_ms`).
      - `reasoning_text`: the agent's fuller reasoning/output text (the
        same value already carried by `TraceStep.output` in
        `Ticket.trace_json`, but previously never copied into this
        table — only the short `action` label was).
      - `used_tools_json`: the raw tool names a specialist actually
        called (mirrors `SpecialistResponse.used_tools`).
      - `alternatives_json`: only populated for the planner's own step —
        the actions NOT chosen and why, from `PlanDecision.alternatives_considered`.
      - `evidence_refs_json`: structured, id-addressable evidence
        (`{type, ref_id, label}`) alongside the existing prose
        `evidence_json` — lets a frontend deep-link to the actual
        order/customer/ticket/KB-article row instead of just displaying
        a sentence.

    Issue [SWARM] #78 adds:
      - `depends_on_json`: JSON list of `step_number`s this step's
        execution causally depended on. Explicit rather than assumed —
        `investigations.py::_build_graph()` previously derived edges from
        step order alone (correct today, since the pipeline never fans
        out, but only an assumption). `orchestrator.py` now sets this
        explicitly per branch, so a future fan-out/fan-in change would
        only need to set different values here, not rewrite the graph
        builder's assumptions.

    Issue [CRITIC] #108 adds:
      - `critic_review_json`: nullable, a single `{agrees, confidence,
        alternative_hypothesis, reasoning}` object (NOT a list, unlike
        every other `*_json` column here) — only ever populated on the
        Critic Agent's own step (`agent_name == "critic"`), same
        one-agent-only convention `alternatives_json` already uses for
        the planner. `None` everywhere else, never a fabricated empty
        review.
    """

    __tablename__ = "investigation_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    investigation_id: Mapped[int] = mapped_column(ForeignKey("investigations.id"))
    step_number: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    agent_name: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="completed")  # completed | failed
    reasoning_text: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    evidence_json: Mapped[str] = mapped_column(String, default="[]")
    evidence_refs_json: Mapped[str] = mapped_column(String, default="[]")
    used_tools_json: Mapped[str] = mapped_column(String, default="[]")
    alternatives_json: Mapped[str] = mapped_column(String, default="[]")
    depends_on_json: Mapped[str] = mapped_column(String, default="[]")
    critic_review_json: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)

    investigation: Mapped["Investigation"] = relationship(back_populates="steps")

    @property
    def evidence(self) -> list[str]:
        return json.loads(self.evidence_json) if self.evidence_json else []

    @property
    def evidence_refs(self) -> list[dict]:
        return json.loads(self.evidence_refs_json) if self.evidence_refs_json else []

    @property
    def used_tools(self) -> list[str]:
        return json.loads(self.used_tools_json) if self.used_tools_json else []

    @property
    def alternatives_considered(self) -> list[dict]:
        return json.loads(self.alternatives_json) if self.alternatives_json else []

    @property
    def depends_on(self) -> list[int]:
        return json.loads(self.depends_on_json) if self.depends_on_json else []

    @property
    def critic_review(self) -> dict | None:
        return json.loads(self.critic_review_json) if self.critic_review_json else None


class Notification(Base):
    """Backs issue #21 (customer notification on booking edit).

    Deliberately NOT a real email/SMS send — see
    app/services/notifications.py's module docstring for why. This table
    is the durable, queryable record of "a notification was sent" (visible
    in the Staff Dashboard's booking drawer, and easy to assert against in
    tests) that a real provider integration would sit behind later without
    changing anything that calls `notify_customer_of_booking_edit`.
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    subject: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ShopifyIntegration(Base):
    """Real Shopify store connection — Settings -> Integrations. See
    app/services/shopify_service.py for what actually talks to Shopify's
    Admin REST API using this row's credentials, and
    app/api/integrations.py for the connect/disconnect/status endpoints
    that write/read it.

    Single-row by convention, not by schema constraint: this is a
    single-tenant demo app (one store, like every other external
    dependency here — see mock_tools.py's fixed seeded data), so nothing
    enforces "only one row" at the DB level, but every reader/writer in
    this codebase treats "the most recently created row" as THE
    connection, same spirit as CustomerMemory being "one row per
    customer" by convention rather than a composite key.

    `access_token` is stored in plain text. This is the same trust
    boundary every other credential in this codebase already lives at
    (see app/config.py's own header: "reads from environment variables
    ... nothing here should ever hold a REAL secret value" — this table
    is the one deliberate exception, since a real Shopify token has to
    live somewhere to make real API calls). A production deployment
    would encrypt this column or use a secrets manager; flagged here
    explicitly rather than silently assumed safe, matching this
    project's convention of naming a scope limit instead of quietly
    living with it (e.g. issue #91's KB section-granularity note).
    `GET /api/integrations/shopify/status` never returns this value —
    see that endpoint's own docstring.
    """

    __tablename__ = "shopify_integrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_url: Mapped[str] = mapped_column(String)
    access_token: Mapped[str] = mapped_column(String)
    # connected | disconnected | error — "error" means the stored
    # credentials were once valid enough to save but a later call failed
    # (e.g. token revoked on Shopify's side); status/status endpoints
    # distinguish this from "never connected" so staff know to reconnect
    # rather than assume the integration was never set up.
    status: Mapped[str] = mapped_column(String, default="disconnected")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Channel(Base):
    """[Omnichannel] issue #132 — the authoritative list of channels
    Servora can receive messages on (Live Chat, Email, WhatsApp,
    Instagram, Facebook Messenger). One row per channel, not a hardcoded
    Python list, so status/config can change without a deploy — see
    app/api/channels.py (issue #135) for the read/write endpoints.

    `key` is the stable slug that `Ticket.channel_key` /
    `Investigation.channel_key` (issue #133) actually store — those
    columns are deliberately NOT a foreign key to this table's `id` (see
    their own docstrings): a conversation's channel attribution must
    survive even if this table were ever re-seeded, same reasoning
    `ShopifyIntegration` already documents for why some relationships in
    this codebase are convention rather than a hard DB constraint.

    Seeded once, at `seed_if_empty()` time, with exactly 5 rows — see
    app/db/seed.py. Real transport for WhatsApp/Instagram/Messenger is
    out of reach in this environment (Meta business verification/app
    review) and is mocked at the integration layer in a later
    Omnichannel phase; this table itself holds no such distinction —
    every channel is equally real data here, only `status` (most
    starting "not_configured") reflects what's actually usable today.
    """

    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)  # live_chat|email|whatsapp|instagram|messenger
    # Defaults to "" (not required at construction time) so a bare
    # Channel(key=...) never errors — every seeded row above sets a real
    # one explicitly.
    display_name: Mapped[str] = mapped_column(String, default="")
    # active | inactive | not_configured
    status: Mapped[str] = mapped_column(String, default="not_configured")
    config_json: Mapped[str] = mapped_column(String, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def config(self) -> dict:
        return json.loads(self.config_json) if self.config_json else {}


class User(Base):
    """[RBAC] issue #172 — a minimal staff-identity table.

    Originally deliberately NOT a real login system (no password
    hashing, no session, no JWT) — real auth has since been added (see
    `Credential`/`AuthSession` below and `app/auth/password.py`) rather
    than kept out forever. The identity row itself is unchanged: a
    staff member's real password lives in `Credential`, not a column
    here, so an existing `User` row (and every seeded/admin-created one)
    never needed a schema change to grow real credentials.

    Customers do NOT get a row here — an existing `Customer` row already
    IS "the customer role" (see app/auth/dependency.py::get_current_actor()),
    so no new customer-identity table exists either; `Credential`/
    `AuthSession` reference a `Customer.id` the same way for that case.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True)
    # support_agent | manager | administrator — see app/auth/roles.py.
    # A plain string column, not a FK to a Role table, same convention
    # every other fixed-vocabulary column in this file already uses.
    role: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Credential(Base):
    """Real login credential — one row per Customer or staff User that
    has ever set a password. A NEW table, not a `password_hash` column
    added to `Customer`/`User` directly: this repo has no migration
    tool (`Base.metadata.create_all()` only creates missing tables, it
    doesn't ALTER an existing one — see the standing note in
    CLAUDE.md), and this app's real deployment is a persistent Postgres
    database where "just delete the file and reseed" isn't an option.
    A brand-new table sidesteps that entirely: `create_all()` adds it
    cleanly to an existing database, dev or prod, no migration needed.

    `actor_type` + `actor_id` (not a single FK) because the referenced
    row lives in one of two different tables depending on the type —
    the same reason `Investigation.channel_metadata`-style polymorphic-
    reference columns already exist elsewhere in this file; a real FK
    can't point at "whichever table this row happens to belong to."
    """

    __tablename__ = "credentials"
    __table_args__ = (UniqueConstraint("actor_type", "actor_id", name="uq_credential_actor"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_type: Mapped[str] = mapped_column(String)  # "customer" | "staff"
    actor_id: Mapped[int] = mapped_column(Integer)
    password_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuthSession(Base):
    """A real, server-side, revocable login session — the opaque bearer
    token `POST /api/auth/login`/`/register` hands back, and the ONLY
    thing `get_current_actor()` trusts to resolve identity now (see its
    own docstring). Deliberately a DB table instead of a signed/stateless
    JWT: no new crypto dependency, and logging out (or an admin revoking
    a session) is a real `DELETE`, not "wait for the token to expire" —
    genuinely revocable, matching how a real login system should behave,
    not just look like one."""

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    actor_type: Mapped[str] = mapped_column(String)  # "customer" | "staff"
    actor_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class SystemSetting(Base):
    """[RBAC] issue #204 — a genuinely new, minimal admin settings
    surface. There is no existing "system configuration" concept in this
    codebase (app/config.py is environment-variable-driven, read once at
    process start, not a runtime-editable table) — this is an honest,
    small, real DB-backed key-value table, not a fabricated wrapper
    around env vars that were never meant to be edited live. Same flat
    key-value shape convention `Channel.config_json` already uses
    elsewhere, just as its own table rather than nested JSON, since these
    values are meant to be individually listed/edited, not read as one
    blob.
    """

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
