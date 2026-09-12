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

Classifier, Planner, and all four specialists (Billing, Technical, Order,
Account) are implemented (issues #3, #4, #6-#9). Only Verification,
Escalation, and Memory in `backend/app/agents/*.py` are still **stubs** —
the pipeline runs end-to-end today regardless (see
`backend/tests/test_health.py`), each remaining stub returns a
placeholder with a `# TODO(issue: ...)` pointing at the GitHub issue that
replaces it. Do not change a function's signature / return shape without
updating `orchestrator.py` and the frontend trace rendering — several
issues depend on the current contracts (the Planner's already changed
once, adding `customer_id`/`db` params — see PR #34 for why). All four
specialists kept their `resolve_x(db, customer_id, message) ->
SpecialistResponse` shape as originally stubbed, and share a private
`_run_specialist()` helper in `specialists.py` — only the system prompt
differs per specialist.

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
