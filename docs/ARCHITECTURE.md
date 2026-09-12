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
`app.tools.tool_registry.build_tool_registry(db)` — so they can ground
every factual claim through a real database query instead of answering from
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
