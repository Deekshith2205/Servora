# Demo Script

Issue #22's deliverable: the exact steps to run the six core scenarios
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

## Scenarios
- [Scenario 1 — Autonomous resolve](#scenario-1--autonomous-resolve)
- [Scenario 2 — Multi-step investigation + action](#scenario-2--multi-step-investigation--action)
- [Scenario 3 — Escalation with full handoff](#scenario-3--escalation-with-full-handoff)
- [Scenario 4 — Genuine parallel multi-agent investigation](#scenario-4--genuine-parallel-multi-agent-investigation)
- [Scenario 5 — Critic Agent: an independent second opinion](#scenario-5--critic-agent-an-independent-second-opinion)
- [Scenario 6 — The Multi-Channel Journey](#scenario-6--the-multi-channel-journey)

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
4. All scenarios below are run from the **Customer Chat** tab, as
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

## Scenario 4 — Genuine parallel multi-agent investigation

**What it shows:** this is the single clearest proof that Servora
*coordinates* multiple agents rather than just running one agent per
ticket — two specialists investigating two different systems at once,
reconciled into one answer. Issue #88.

1. In Customer Chat, type the issue's own original example:
   > Payment deducted but order not created
2. **Expected:** the Planner recognizes this spans two domains — a
   payment fact (billing) and a fulfillment fact (order) — and sets
   `additional_agents` alongside its primary `target_agent`. The
   orchestrator then runs BOTH specialists **concurrently, each on its
   own database session** (not sequentially), and reconciles their two
   independent, grounded findings into one reply, clearly labeled
   ("Billing specialist: ... Order specialist: ..."). This is genuinely
   real: verified live against a real Gemini call, the Billing specialist
   found and refunded a payment/fulfillment mismatch while the Order
   specialist independently investigated the same order from the
   fulfillment side — two real tool-calling investigations, not a
   scripted split.
3. Switch to the **Agent Swarm** tab. This is the payoff shot: the graph
   shows **Billing Agent** and **Order Agent** side by side in a single
   column with a red **PARALLEL** badge, both fed by the same Planner
   step, both flowing into a shared **Reconciliation** node — a real
   fan-out/fan-in shape, not the usual straight line. Click each
   specialist node to show they ran fully independent investigations
   (different tools, different evidence).
4. Point out the Reconciliation step's confidence is the **lower** of the
   two specialists' — deliberately conservative, so one weakly-grounded
   finding can't be hidden behind the other's higher confidence.

## Scenario 5 — Critic Agent: an independent second opinion

**What it shows:** the system checking its own work, not just trusting a
specialist's first answer. Issue #109/#110.

1. In Customer Chat, type any message that resolves through a specialist
   (Scenario 1's or Scenario 2's message both work). After it resolves,
   the Investigation timeline now shows a **Critic** step between the
   specialist and Verification.
2. Switch to the **Investigation Board**, select that investigation, and
   scroll to the **Critic Review — Independent Second Opinion** card
   (right after the Resolution card). Point out it's a genuinely separate
   LLM call reviewing the root cause, evidence, and resolution — not the
   same specialist restating its own answer — with its own confidence
   score and specific reasoning citing the actual evidence gathered.
3. Note (verified live): the critic doesn't always just agree — it can
   flag a gap and propose a real **Alternative Hypothesis**, shown struck
   through in red when it disagrees. Either outcome is a legitimate,
   real review, not a scripted "always agrees" rubber stamp.
4. Point out **Agent Performance Metrics** at the bottom now tracks
   "Critic" as its own agent (avg duration, avg confidence) — this came
   for free from the existing cross-investigation aggregate, no new
   dashboard needed.

## Scenario 6 — The Multi-Channel Journey

**What it shows:** the agent maintaining context across different channels, and the Staff Dashboard displaying a unified view of the customer's cross-channel interactions. Issue #163.

1. **Prerequisite**: This scenario uses the seeded WhatsApp message from `app/db/seed.py`. Do NOT run Scenario 1 before this, as it may change the state of the customer's tickets.
2. Go to the **Inbox** tab and locate Alice Rao's open WhatsApp ticket. The subject is "Bluetooth Speaker still processing".
3. Open the ticket and observe the actual message:
   > Hi! Just checking in on my Bluetooth Speaker order, it's still showing processing.
4. From the **Inbox**, switch to the **Staff Dashboard** and open an escalation for Alice (e.g. from Scenario 3) or click into her details.
5. Scroll down to the **Customer Profile** section in the drawer. Point out the **Channels Used** badge list — a visual summary proving Alice has interacted across multiple distinct channels (Live Chat, WhatsApp, Messenger).
6. Look at the **Conversation History** list directly below it. Point out that the previous tickets are listed newest-first, and each ticket has a distinct **channel badge** (e.g., Live Chat, WhatsApp, Messenger) right next to the Ticket ID. This demonstrates a true omnichannel history without requiring the agent or staff to check different systems.

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
  [EXPLAIN] batch, #77-#98): reuses Scenario 2's exact duplicate-charge
  message.
  1. **Before** sending Scenario 2's message again, switch to the
     **Agent Swarm** tab first and leave it open — issue #79 made this
     tab genuinely live, not a replay. Then go back to **Customer Chat**
     and send the message. Switch back to **Agent Swarm** immediately
     (don't wait for the reply): if the pipeline hasn't finished yet
     you'll see a red **LIVE** entry at the top of "Recent
     Investigations" with real agent nodes appearing one at a time as
     they actually complete — this is genuinely real-time (SSE), not a
     timer. **Timing note**: this demo customer's seeded ticket history
     is deliberately rich, so several scenarios resolve or escalate in
     as little as 3-4 seconds — switch tabs quickly, or narrate that the
     live view is what a slower/larger pipeline run would show more of.
  2. Once it finishes (LIVE hands off to the completed record
     automatically), point out the node/edge graph is the SAME real
     investigation just created — not a separate diagram — rendered
     left-to-right in real execution order (Classifier → Planner →
     Billing → Verification → Memory), each node showing a real
     Idle/Running/Completed/Failed status (#83) and its real confidence/
     duration. Click the **Billing Agent** node to expand its card: real
     reasoning, the exact tools it called (`get_customer_orders`,
     `check_payment_issue`, `issue_refund`), and the evidence each one
     produced.
  3. Point out the **Swarm Timeline** strip below it (#84) — the same
     steps as a Gantt-style bar, width proportional to real execution
     time, and the **REPLAY** speed control (0.5x/1x/2x/Instant, #85) in
     the top-right of the graph card — useful for re-watching a past
     investigation without waiting through it in real time.
  4. Back in **Customer Chat**, click **"Why did Servora recommend
     this?"** under the reply. Point out, in order: the large confidence
     gauge (90%) with a per-agent breakdown underneath (not just one
     number); the Decision Rationale paragraph; **Alternative Actions
     Considered** — the "Chosen" badge next to the real action taken
     (`resolve`), with the OTHER two actions (`clarify`, `escalate`) shown
     struck through alongside the specific reason each was rejected —
     this is the Planner's actual deliberation, not a fabricated list of
     options; the **Decision Tree** (#97) showing the same branch
     visually, plus a second Verification pass/fail branch point; and
     the **Evidence Explorer** (#95) — click any evidence card (an order,
     a customer, a KB article) to see a real inline preview fetched live
     from the database, not a static string.
  5. The same panel, in full-page form, is also in the **Staff
     Dashboard**'s escalation drawer for any escalated ticket (Scenario
     3) — worth showing once to make clear it's one shared component, not
     a customer-only feature.
