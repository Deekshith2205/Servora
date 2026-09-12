# Servora — Architecture

Autonomous customer support system: understands intent, investigates across
data sources, takes real actions, and escalates to a human with full
context. Graded on four pillars — **context retention, reasoning,
automation, human handoff** — every agent below exists to demonstrate one
or more of these, not just to answer questions.

## Agent graph

```
Customer message
      │
      ▼
[Classifier Agent] → category, urgency, sentiment + reasoning (not just a label)
      │
      ▼
[Planner Agent] → resolve / clarify / escalate
      │
      ▼
  specialist agents (billing / technical / order / account)
      │  tool-only answers — a specialist must call a tool for any factual
      │  claim (order status, policy, refund) and never answer from model
      │  memory alone. This is what stops it hallucinating in front of
      │  judges.
      ▼
[Verification Agent] — checks the proposed resolution before it's shown to
      │                 the customer or executed. Failing verification
      │                 routes back to the Planner or to Escalation.
      ▼
[Memory Writer] — summarizes the turn and set-union merges it into the
      │            customer profile. Never overwrite: an empty/failed
      │            extraction is a no-op, not an erasure.
      ▼
Resolved ── OR ── [Escalation Agent] → structured handoff packet:
                     Situation / Attempted Fixes / Root-Cause Hypothesis /
                     Recommended Action / Urgency
                   → human agent (Staff Dashboard)
      │
      ▼
[Learning Agent] — mines resolved/escalated tickets for KB gaps and
                    routing mistakes (future: drafts KB article updates
                    for human approval)
```

## Why this shape

Researched against several open-source customer-support agent projects on
GitHub before settling on this graph — see the chat history / team notes
for the comparison. Two patterns worth calling out because they're easy to
skip under time pressure and expensive to bolt on later:

1. **Verification before closure.** Most simple demos skip straight from
   "specialist answered" to "show the customer." A distinct verification
   step is what makes the system's reasoning legible instead of trusting
   the first agent's output blindly.
2. **Memory as merge, not overwrite.** Every turn should add to what's
   known about a customer, never silently erase it because one LLM call
   returned nothing useful.

## Booking state machine (hotel voice-receptionist stretch feature)

```
AI_DRAFTED → STAFF_REVIEWED → CONFIRMED
```

Every transition is logged; any edit made after `AI_DRAFTED` triggers a
customer notification with a diff of what changed (room type, dates,
price). See the `Booking` model in `backend/app/db/models.py`.

## Current state of this repo

All of P0 and P1 are implemented (issues #3, #4, #6-#11), and P2 is
underway: the Escalation Agent (#12) now builds a real `HandoffPacket` at
both points a conversation escalates. `docs/ARCHITECTURE.md`'s "Current
state" note stays scoped to `backend/app/agents/*.py` — see `CLAUDE.md`
for exactly which numbered issues are merged vs. open at any given
moment; that file is the one kept current session-to-session. Do not
change a function's signature / return shape without updating
`orchestrator.py` and the frontend trace rendering — several issues
depend on the current contracts (the Planner's already changed once,
adding `customer_id`/`db` params — see PR #34; `memory.py`'s
`load_profile`/`merge_profile` gained a `db` param too — see PR #41).
All four specialists kept their `resolve_x(db, customer_id, message) ->
SpecialistResponse` shape as originally stubbed, and share a private
`_run_specialist()` helper in `specialists.py` — only the system prompt
differs per specialist. Verification's `verify(response) ->
VerificationResult` also needed no contract change — the original stub
signature was already exactly what `orchestrator.py` calls.
`ChatResult` (orchestrator.py) gained a `handoff_packet` field (#12,
default `None` — additive, not a breaking change).

**Bug fixed alongside #11**: `_run_specialist()` never actually told the
model the customer's ID — every specialist tool call that needs one
(`get_customer_orders`, `get_customer`, ...) was relying on the model to
guess it. Wiring in the customer-memory context (#11) touched this exact
code path, so it was fixed at the same time. This had gone unnoticed
because no session verifying these issues has had a real Anthropic API
key — see the real-key verification gap tracked in `CLAUDE.md`.

### Escalation Agent (Issue #12 — implemented)

`build_handoff_packet()` takes the trace-so-far as `attempted_fixes`, the
classifier's `urgency`, and (when a specialist ran) its `confidence`, and
makes one LLM call to produce `situation` / `root_cause_hypothesis` /
`recommended_action` — the fields that actually need summarizing.
`attempted_fixes` and `urgency` are passed straight through, not derived
by the LLM. Scope note: this agent doesn't decide *whether* to escalate
(that's already Planner/Verification's job) — it turns an
already-made decision into something a human can act on. Issue #13
exposed the packet via the API and the customer chat bubble; issue #14
(below) persists it against a real Ticket for the Staff Dashboard.

### Staff Dashboard ticket history (Issue #14 and #58)

Before these changes, `/api/chat` never created or touched a `Ticket` row at all —
the Staff Dashboard's queue only ever showed the seeded demo tickets from
`db/seed.py`. Now, `orchestrator.py::_create_ticket()` persists
a real `Ticket` at both escalation points and at the successful resolution point.
Escalated conversations are saved with `status="escalated"` and contain both 
the reasoning trace and handoff packet JSON-encoded onto two nullable columns
(`Ticket.trace_json`, `Ticket.handoff_packet_json`). Resolved conversations 
are saved with `status="resolved"` and contain the trace JSON.

### Escalation Workspace (Issue #63)

The Staff Dashboard escalation drawer has been expanded into a complete support workspace:
- **Customer context:** Displays the customer's actual profile (Name, Email, Phone, Tier) and recent ticket history (excluding the currently active ticket).
- **Assignment:** Supports a lightweight `assigned_to` demo free-text field without an authenticated identity model.
- **Administrative Close:** Support staff can close a ticket out of the active queue without invoking the AI/KB resolution workflow.
- **Status semantics:**
  - `open` / `escalated` = active support queue.
  - `resolved` = completed resolution workflow (AI-assisted or human).
  - `closed` = administrative closure, excluded from the escalation queue and analytics (only resolved + escalated are counted).

`GET /api/escalations` only returns open/escalated tickets.
`GET /api/tickets/resolved` remains explicitly for resolved history.
`GET /api/escalations/{id}` returns the enriched detail (trace, packet, customer, history, assignment).

**Real bug found while writing this issue's tests, fixed in the same
PR**: `test_health.py`/`test_tickets_api.py` both instantiate a bare
`TestClient(app)` at module level — this does **not** reliably trigger
FastAPI's ASGI lifespan (`Base.metadata.create_all()` +
`seed_if_empty()`) in this environment; only `with TestClient(app) as
client:` is guaranteed to. Every test written before #14 happened to
avoid this gap (every DB-touching agent was mocked, or the test built
its own isolated in-memory engine directly) — #14's tests are the first
to need real seeded data through a bare `TestClient`, which is what
surfaced it. Fixed with `tests/conftest.py`: a `pytest_configure` hook
that creates+seeds the schema once before any test runs, independent of
whichever TestClient pattern a given test file uses. This is the second
bug of this shape found this way — see the customer-ID fix noted above
(#11) — both are exactly the kind of gap the long-standing real-API-key
verification issue (tracked in `CLAUDE.md`) exists to catch.

### Verification Agent (Issue #10 — implemented)

`verify()` runs two deterministic checks — no second LLM call, so it's
network-free to test and instant in production: a confidence threshold
(0.5, see `specialists.py::_estimate_confidence()`), and a narrow
"completed-action" phrase check that catches a reply claiming e.g. "I've
issued a refund" when `issue_refund` was never actually called. This is
a documented approximation, not a semantic check — a real
second-LLM-judge pass would catch more, at the cost of another network
call per verification.

### LLM tool-calling (Issue #5 — implemented)

`backend/app/llm.py::call_llm()` now supports an optional `tools` argument
that drives a full Anthropic tool-calling loop. Specialist agents pass
`(tool_schemas, tool_handlers)` — obtained from
`app.tools.tool_registry.build_filtered_tool_registry(db, specialist)` (see
"Specialist tool permissions" below for why it's the *filtered* factory,
not the generic `build_tool_registry(db)`) — so they can ground every
factual claim through a real database query instead of answering from
model memory.

Rules:
- Specialists must use `call_llm(..., tools=...)` for any factual claim;
  never call the Anthropic SDK directly.
- All normal automated CI tests (`pytest`) are **network-free** and do not
  require `ANTHROPIC_API_KEY`. The tool-calling loop is tested by mocking
  the Anthropic client.
- The manual real-API smoke test lives in
  `backend/scripts/check_tool_calling.py`. Run it with a real key before
  opening a PR that changes the tool-calling infrastructure.

### Specialist tool permissions (Issue [P6] — implemented)

**Problem this closes:** every specialist previously called the generic
`build_tool_registry(db)` and received the FULL set of tools — including
`issue_refund` — with only each specialist's system prompt (in
`specialists.py`) instructing it which tools it should actually use. A
system prompt is not an authorization boundary. An LLM can misread its
own instructions, a future prompt edit can quietly loosen what it
"should" do, or a genuinely adversarial input can attempt to get a model
to act outside its intended role — none of that should be able to turn
into the read-only Account specialist actually issuing a refund. The
fix has to live in application code that runs regardless of model
behavior, not in wording the model is merely asked to obey:

> Bad: "Account agents should never call issue_refund" (a sentence in a
> prompt). Good: the Account agent's tool registry literally does not
> contain `issue_refund`, and the execution layer rejects it even if an
> invalid tool name somehow reaches the executor.

**The mapping.** `app.tools.tool_registry.SPECIALIST_TOOL_PERMISSIONS` is
the single authoritative specialist → allowed-tool-names mapping:

| Specialist | Allowed tools |
|---|---|
| `billing` | `get_customer`, `get_customer_orders`, `check_payment_issue`, `search_kb`, `issue_refund` |
| `technical` | `get_customer`, `get_customer_tickets`, `search_kb` |
| `order` | `get_customer`, `get_customer_orders`, `check_order_issue`, `search_kb` |
| `account` | `get_customer` (read-only — its entire allowlist) |

`check_room_availability` is in nobody's allowlist here — it belongs to
the separate hotel-booking stretch feature (`app/agents/booking.py`),
which has its own dedicated registry (`app/tools/booking_tools.py`) and
never touches this one; none of the four support specialists should
reach it either way.

**Enforcement — two levels, both in code:**

1. **Tool exposure.** `build_filtered_tool_registry(db, specialist)`
   filters the generic registry's schemas down to just that specialist's
   allowed tools *before* `call_llm()` ever runs. The LLM is never shown
   a schema for a tool outside its allowlist — it cannot request
   something it was never told exists.
2. **Tool execution.** The same filtering also applies to the handler
   dict passed into the tool-calling loop. If a tool_use block somehow
   names an unauthorized tool anyway (a hallucinated name, one copied
   from an earlier turn, or a deliberately adversarial prompt), it is
   simply not a key in that specialist's `tool_handlers` — `call_llm()`'s
   existing "unknown tool" handling (already there for issue #5, already
   tested) rejects it with a deterministic `tool_result` error and never
   invokes the underlying handler. That existing mechanism is reused
   rather than duplicated: a filtered handler dict makes "unauthorized"
   and "doesn't exist" indistinguishable to the model, which is the more
   secure posture — it never even learns that a restricted tool exists.

The generic, unfiltered `build_tool_registry(db)` is kept exactly as it
was — `backend/scripts/check_tool_calling.py` and `tests/test_tools.py`
both still use it directly and still pass unmodified, since it's a
legitimately useful building block (the filtered factory is built on
top of it) for anything that genuinely needs the full tool set (a
one-off script, a future admin-only agent, etc.), not something this
change removes.

`_run_specialist()` (`specialists.py`) gained one new keyword-only
parameter, `specialist: str`, so it knows which allowlist to apply — the
only contract change this issue needed. Each of the four public
`resolve_billing/technical/order/account()` functions kept their exact
existing signature; they just now pass their own name through. A
rejected tool attempt still appears in `used_tools`/the reasoning trace
(the attempt log in `call_llm()` records what was *attempted*, not only
what succeeded) — so an unauthorized attempt is auditable even though it
never executed.

See `backend/tests/test_tool_permissions.py` for the full proof: each
specialist's exact allowed set (schemas AND handlers), the actual
Anthropic call kwargs a mocked client receives per specialist (proving
the LLM itself never sees an unauthorized schema, not just that the
mapping says so), and an end-to-end defensive-execution test that
scripts a fake model attempting `issue_refund` as the Account
specialist and confirms the order in the database is untouched.

### Support Intelligence Analytics (Issues #15 and #62)

The `GET /api/analytics/summary` endpoint provides the data backing the Analytics dashboard.
It aggregates data across a consistent **30-day window**. The following metrics are provided:
- **Recurring Issues**: Root-cause clusters built using deterministic similarity matching on ticket themes and text overlap (Issue #15).
- **Churn Signals**: Identifies customers with multiple still-unresolved (open or escalated) tickets (Issue #16).
- **Ticket Volume Trend**: A zero-padded array of daily ticket creation counts (Issue #16).
- **Resolution & Escalation Rates**: Derived strictly from *processed* conversations within the 30-day window (`resolved` + `escalated`). Open tickets are excluded from the denominator to prevent distorting outcome rates, as they are not yet completed by the pipeline.
- **Classifier Confidence Distribution**: Groups classifier scores (`Ticket.confidence`) into high (>= 0.80), moderate (0.60-0.79), and low (< 0.60). Legacy or seed records with `NULL` confidence are correctly excluded from the denominator.

### Billing Agent & Payment Anomalies (Issue #59)

The Billing Agent operates on an `Order` model that distinctly separates payment state from fulfillment state to accurately reason about payment issues:
- `payment_status` (`paid`, `failed`, `refunded`) vs `status` (`processing`, `shipped`, `delivered`, `failed`, `refunded`)
- `duplicate_of`: Nullable self-referencing foreign key explicitly linking a duplicate charge to its original order.

The agent uses the `check_payment_issue` deterministic tool before taking action to catch:
- **Duplicate payment**: Detected via the `duplicate_of` relationship. The agent will refund only the duplicate and leave the original intact.
- **Payment/Fulfillment mismatch**: Detected when `payment_status="paid"` and `status="failed"`. The agent will avoid issuing an automated refund and follow escalation/remedy procedures instead.

Refund Idempotency is strictly enforced at the data layer—an already refunded order cannot be refunded again, protecting against double refunds even if the LLM attempts it.

Structured Root Causes (e.g. "Duplicate payment detected...") are generated deterministically from the tool result wrapper in `specialists.py` and threaded cleanly through the `TraceStep` to be visualized in the frontend InvestigationTimeline without resorting to LLM XML generation.

### Order Agent & Inventory Anomalies (Issue #60)

The Order Agent tracks order anomalies, specifically distinguishing between standard processing delays and true failures:
- **Order Cancellation**: Detected when `status="cancelled"`. The order is halted; it is not simply delayed.
- **Inventory Shortfall**: Detected when `status="failed"` and `failure_reason="inventory_shortfall"`. The order cannot be fulfilled due to lack of stock.

The agent uses the `check_order_issue` deterministic tool *before* assessing any tracking delays. This prevents the agent from hallucinating "delayed in transit" states for cancelled or failed orders.
Like the Billing Agent, structured Root Causes and Resolutions are generated deterministically from the tool result wrapper and threaded through the `TraceStep` for the frontend InvestigationTimeline.

### Investigation Board (Issue [FEATURE] "AI Investigation Board & Autonomous Reasoning Timeline")

**Goal:** make the multi-agent reasoning that already happens on every
conversation visible on its own dedicated page, not just as a collapsible
panel next to a chat bubble — a normalized, queryable record of what
Servora investigated, what evidence it found, and why it decided what it
decided.

**Data model — additive, not a replacement.** `Ticket.trace_json` (issue
#14) still exists and is written exactly as before. Alongside it,
`orchestrator.py::_persist_investigation()` writes one `Investigation`
row (1:1 with the `Ticket` — `started_at`/`completed_at`, `status`,
`confidence_score`, `root_cause`, `resolution`) and a normalized
`InvestigationStep` row per pipeline stage (`step_number`, `agent_name`,
`action`, `status`, `evidence_json`, `duration_ms`, `confidence`). Why a
second table rather than parsing `trace_json` harder: the Board's "Agent
Performance Metrics" section needs a real cross-investigation
`GROUP BY agent_name` (avg duration, avg confidence, total runs) —
that's a SQL query over `InvestigationStep`, not an in-Python scan of
every ticket's JSON blob.

**Evidence — derived from real tool results, never placeholder text.**
`specialists.py::_run_specialist()` wraps every tool handler in the
specialist's (permission-filtered — see the section above) registry to
capture a short, human-readable string per real tool call —
`_describe_evidence()` reads the actual `Order`/`Customer`/`KBArticle`
objects or dicts `mock_tools.py` returns (e.g. "Retrieved 2 order(s) for
customer #1: #4, #5.", "Payment anomaly detected on order #5:
duplicate_payment."). `SpecialistResponse` gained one additive
`evidence: list[str]` field carrying these; `orchestrator.py` attaches
them to that step's `InvestigationStep.evidence_json`.

**API** (`app/api/investigations.py`, read-only):
- `GET /api/investigations` — recent investigations, newest first (the
  Board's browse list).
- `GET /api/investigations/{id}` / `GET /api/investigations/by-ticket/{ticket_id}`
  — full detail: `root_cause`, `confidence`, `status`, `timeline`
  (ordered `InvestigationStep`s), a per-investigation `agents` rollup,
  and a flattened `evidence` list.
- `GET /api/investigations/metrics/agents` — the cross-investigation
  aggregate described above.

**A real bug found wiring this up**: `orchestrator.py`'s `ChatResult` has
carried a real `ticket_id` since issue #14, but `app/api/chat.py`'s
`ChatResponse` never actually included it — the frontend had no way to
link a just-completed conversation to its ticket (or now, its
Investigation) without a separate, fragile lookup. Fixed by adding
`ticket_id` to `ChatResponse` (additive, optional — no existing caller
breaks).

**Honest limitation, not silently glossed over: `/api/chat` is fully
synchronous.** The whole classify → plan → specialist → verify →
(escalate|resolve) pipeline runs to completion inside one request before
anything is returned — there is no genuine in-progress, streaming state
to subscribe to today. The frontend's Investigation Board (`frontend/
src/pages/InvestigationBoard.jsx`) is upfront about this in its own
module docstring: it fetches an already-complete investigation and
replays its real steps with a staggered reveal animation (an "Agent
Activity Feed" and a checklist-style timeline both animate in over
~450ms per step) so watching it still *feels* like observing the agents
work — using entirely real, already-persisted data, never mock content.
Genuinely live, server-pushed progress (SSE/WebSocket streaming from
inside `handle_message()`) would be a legitimate, larger follow-up if
truly real-time updates are wanted later.

**Scope note**: the four "bonus, if feasible" items from the original
feature request (agent swarm visualization, an investigation dependency
graph, and a replay *mode* distinct from the reveal animation above)
were not built — the seven required Board sections (Status, Agent
Activity Feed, Timeline, Evidence, Root Cause, Resolution, Escalation
Summary) plus Agent Performance Metrics were the scoped deliverable.
