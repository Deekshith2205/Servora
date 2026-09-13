# Demo Script

Issue #22's deliverable: the exact steps to run the three core scenarios
judges should see, plus what each one is meant to demonstrate. Written so
anyone on the team can run this cold, without having read the rest of the
codebase first.

**Every scenario below is driven by a real LLM call** (classifier, planner,
specialist, escalation) — see [`CLAUDE.md`](../CLAUDE.md)'s Open Questions:
no session that built this project has ever run it against a real
Anthropic API key. Set `ANTHROPIC_API_KEY` in `backend/.env` before the
demo (copy `backend/.env.example`) — without it, every message will
degrade to a "Failed to fetch"-style error explaining the missing key
(fixed to be readable rather than opaque as of issue #17). The expected
outcomes below describe what the system is *designed* to do per each
agent's system prompt — real model output can vary in wording, though the
underlying tool calls and routing decisions should be consistent.

## Setup

1. Follow [`CONTRIBUTING.md`](../CONTRIBUTING.md) to get both servers
   running (`uvicorn` on :8000, `npm run dev` on :5173).
2. **Delete `backend/servora.db` before starting** if one already exists
   from before this issue — `Base.metadata.create_all()` does not add new
   seed rows or migrate schema for an existing SQLite file (a known,
   documented gap; see CLAUDE.md). A fresh file reseeds automatically on
   the next backend startup.
3. Open the app at `http://localhost:5173/app` (the marketing landing
   page is a separate route — the demo happens in the actual product).
4. All three scenarios below are run from the **Customer Chat** tab, as
   "Demo Customer #1" (Alice Rao) — that customer ID is hardcoded in
   `CustomerChat.jsx` today, which is why every scenario is written
   around her rather than the second seeded customer (Bob).

## Scenario 1 — Autonomous resolve

**What it shows:** the simplest end-to-end case — investigate, ground the
answer in a real tool call, resolve, no human needed.

1. In Customer Chat, type:
   > Where is my order? What's the status of my headphones?
2. **Expected:** the Classifier tags this `order`/low-to-moderate urgency;
   the Planner routes to the Order specialist; the specialist calls
   `get_customer_orders`, finds the seeded "Wireless Headphones" order
   (status `shipped`), and replies citing that status directly — no
   escalation, no hedging language like "let me check" without an actual
   answer.
3. Click **"Investigation details"** under the reply to show the real
   reasoning trace (classifier → planner → specialist), not a canned
   response.
4. Point out the response never invents a tracking number or delivery
   date that wasn't actually in the database — that's the
   tool-only-grounding rule from `docs/ARCHITECTURE.md`.

## Scenario 2 — Multi-step investigation + action

**What it shows:** a specialist that investigates across more than one
source *and* takes a real, irreversible action — not just answering a
question.

1. In Customer Chat, type:
   > I was charged twice for my bluetooth speaker order, can you refund the duplicate?
2. **Expected:** routes to the Billing specialist, which (per its system
   prompt) calls `get_customer_orders` to find the specific order, then
   `search_kb` (the seeded "Refund policy" article) to confirm a refund is
   warranted, then `issue_refund` on that exact order — three tool calls,
   ending in a real state change, not just a lookup.
3. After the reply, switch to the **Analytics** tab and show the order's
   status now reads `refunded` — this isn't a scripted answer, the
   database actually changed.
4. Contrast with Scenario 1: point out the trace here has an extra step
   (an action tool, not just grounding tools) — this is exactly what
   `_estimate_confidence()` in `app/agents/specialists.py` uses to score
   confidence at 0.9 instead of 0.6.

## Scenario 3 — Escalation with full handoff

**What it shows:** the system recognizing a case it should *not* try to
resolve itself, and handing it to a human with complete context — not
just "sorry, a human will follow up."

1. In Customer Chat, type (calm, matter-of-fact wording is deliberate —
   see below):
   > This is the third time this month a package hasn't actually arrived even though it says delivered. Can someone actually look into this properly?
2. **Expected:** the Planner sees two PRIOR, RESOLVED tickets on this
   customer with the same underlying problem (seeded in
   `app/db/seed.py` — "Package never arrived" / "Second package also
   never arrived") and escalates rather than routing to a specialist for
   a third attempt at the same fix, **even though the wording above is
   calm, not angry** — this is the specific case `docs/ARCHITECTURE.md`
   and the Planner's system prompt call out explicitly: sentiment alone
   must not drive the decision.
3. **Expected UI:** the chat reply includes a handoff card (situation /
   likely cause / recommended next step / urgency) — issue #13's
   real `HandoffPacket`, not a generic "we'll get back to you."
4. Switch to the **Staff Dashboard** tab, open the new escalation from the
   queue, and show:
   - The full reasoning trace (classifier → planner → escalation).
   - The same handoff packet, in the staff-facing view.
   - Type a resolution note and click **Mark Resolved** — show the
     Learning Agent's KB-article suggestion (issue #17) that comes back
     (or the honest "no suggestion" message if the model judges it a
     one-off — both are correct outcomes, not a bug).

## Optional bonus material (if time allows)

These aren't part of the required 3-scenario script but are worth a
mention if the demo is going well:

- **Analytics tab**: root-cause clustering (#15) and the churn-risk /
  ticket-volume-trend view (#16) — point out these read from the same
  live ticket data the scenarios above just created, not separate mock
  data.
- **Book a Room tab** (#18/#19, if merged): a full voice-or-text hotel
  booking conversation, ending in a draft booking a staff member reviews
  in the Staff Dashboard's Bookings section (#20) — editing it there
  sends the (mocked, see `app/services/notifications.py`) customer
  notification from issue #21.
- **Agent Swarm tab + "Why did Servora recommend this?"** (the [SWARM]/
  [EXPLAIN] P0 batch, #77-#98): reuses Scenario 2's exact duplicate-charge
  message — after it resolves, this is the moment to switch to it.
  1. Type Scenario 2's message again (or reuse the same conversation) and
     switch to the **Agent Swarm** tab. Point out the node/edge graph is
     the SAME real investigation just created — not a separate diagram —
     rendered left-to-right in real execution order (Classifier → Planner
     → Billing → Verification → Memory), each node showing its real
     confidence and duration. Click the **Billing Agent** node to expand
     its card: real reasoning, the exact tools it called
     (`get_customer_orders`, `check_payment_issue`, `issue_refund`), and
     the evidence each one produced.
  2. Back in **Customer Chat**, click **"Why did Servora recommend
     this?"** under the reply. Point out, in order: the large confidence
     gauge (90%) with a per-agent breakdown underneath (not just one
     number); the Decision Rationale paragraph; **Alternative Actions
     Considered** — the "Chosen" badge next to the real action taken
     (`resolve`), with the OTHER two actions (`clarify`, `escalate`) shown
     struck through alongside the specific reason each was rejected —
     this is the Planner's actual deliberation, not a fabricated list of
     options.
  3. The same panel, in full-page form, is also in the **Staff
     Dashboard**'s escalation drawer for any escalated ticket (Scenario
     3) — worth showing once to make clear it's one shared component, not
     a customer-only feature.
