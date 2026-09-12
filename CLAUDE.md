# Servora — Project Memory

This file is read automatically at the start of every Claude Code session
in this repo. **Keep it current** — it's how a new session picks up exactly
where the last one left off without re-reading old chat history. Update
the Progress Log (and Next Up) at the end of any session that changes
project state; everything else here should only change when a real
decision changes.

## What this is

Autonomous AI customer support system, built for a hackathon's "Customer
Support" track. Judged on **context retention, reasoning, automation, and
human handoff** — not just question-answering. Full problem statement and
feature-idea brainstorm happened in chat before this repo existed; what
survived into an actual decision is captured below and in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

- **Repo:** https://github.com/Deekshith2205/Servora
- **Issues (prioritized backlog):** https://github.com/Deekshith2205/Servora/issues
- **Architecture doc:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Contribution workflow:** [`CONTRIBUTING.md`](CONTRIBUTING.md)

## Stack (decided)

React + FastAPI, split frontend/backend — chosen over a single-file
Streamlit app because the team is 4+ people who need to work in parallel
without stepping on each other's files. See `backend/` and `frontend/`.

## Key decisions already made (don't re-litigate these)

- **Agent graph:** Classifier → Planner → specialist (billing/technical/order/account)
  → Verification → Memory writer, with Escalation reachable from Planner or
  a failed Verification. Full rationale in `docs/ARCHITECTURE.md`.
- **Tool-only grounding:** a specialist agent must call a tool
  (`app/tools/mock_tools.py`) for any factual claim — order status, price,
  policy — never answer from model memory. This is what stops it
  hallucinating live in front of judges.
- **Verification before closure:** a resolution is checked by a distinct
  Verification Agent before it reaches the customer, not trusted on the
  first pass.
- **Memory is merge, not overwrite:** customer profile updates are
  set-union merges; an empty/failed extraction is a no-op, never an
  erasure of a previously known fact.
- **Escalation is confidence-scored, not sentiment-only:** a calm customer
  with an unresolvable issue should still escalate.
- **LLM:** Anthropic, `claude-opus-5` by default (`LLM_MODEL` in `.env`),
  SDK `anthropic==1.5.0`, all calls go through `backend/app/llm.py::call_llm()`
  — never call the SDK directly from an agent.
- **Issue priority scheme:** `[P0]`…`[P5]` prefixes in issue titles (P0 =
  foundation, do first; P5 = polish). Titled this way instead of GitHub
  labels because the repo's write access was blocked at issue-creation
  time — **worth revisiting**: now that push/triage access works, someone
  could add real priority labels and retitle, low priority chore.
  **`[P6]`** was added once the original P0-P5 backlog (#2-#22) was fully
  done — hardening/enhancement issues on top of a complete system, not
  new foundational scope. See the 2026-09-13 P6 progress-log entry.
- **Hotel voice-booking feature (P4, stretch):** browser-mic demo (no
  telephony/Twilio) chosen over a real phone line — avoids live-call risk
  during judging. Booking state machine: `AI_DRAFTED → STAFF_REVIEWED →
  CONFIRMED`, any post-draft edit triggers a customer notification (email
  via the already-connected Gmail account, to avoid a new SMS/email
  provider signup).

## Repo layout

```
backend/    FastAPI + SQLAlchemy (SQLite) + Anthropic SDK
  app/agents/       classifier, planner, specialists, verification,
                     escalation, memory — mostly STUBS, see TODOs
  app/tools/         mock_tools.py — functional DB-backed tool functions
  app/orchestrator.py  wires the agents together, runs end-to-end today
  app/llm.py          the only place that calls the Anthropic SDK
  app/db/seed.py       demo data (customers, orders, tickets, KB, rooms)
frontend/   React + Vite — Customer Chat / Staff Dashboard / Analytics tabs
docs/ARCHITECTURE.md   the agent graph + design rationale, in full
```

## Progress log

### 2026-09-11
- Base scaffold designed (researched several open-source customer-support
  agent repos on GitHub first — see decisions above) and built: FastAPI +
  React scaffold, mock SQLite DB seeded with demo data, full stub agent
  pipeline that already runs end-to-end (`pytest` passing, `npm run build`
  passing). Pushed to `main`.
- 22 GitHub issues created, prioritized P0–P5, each stating its
  dependency on earlier ones.
- Push access was blocked (403) right after the scaffold was built —
  resolved once Deekshith2205 added collaborator access; team should now
  all have push/triage rights.
- **Issue #2** ("[P0] Wire a real LLM provider into the agent stubs")
  implemented: `app/llm.py::call_llm()`, text + structured-output modes,
  bumped `anthropic` 0.34.2 → 1.5.0. PR:
  https://github.com/Deekshith2205/Servora/pull/24 — **merged**. Still
  **not verified against a real Anthropic API key by any session** (none
  available in the environments that built #2 or #3) — see Open
  questions.
- `CLAUDE.md` itself added — PR #25, merged.
- **CI added** on `main` via PR #27 (a teammate's own workflow — a
  near-duplicate I opened as PR #26 was closed in favor of theirs, no
  conflict): `.github/workflows/ci.yml` runs backend `pytest`, frontend
  `npm run lint` + `npm run build`, on every PR/push to `main`. Not yet a
  *required* check — see Open questions.

### 2026-09-12
- **Issue #3** ("[P0] Implement Classifier Agent") implemented:
  `classify()` now calls the real LLM via `call_llm()` with a
  structured-output schema (category/sentiment/urgency/reasoning).
  Contract unchanged, so `orchestrator.py` needed no changes. PR:
  https://github.com/Deekshith2205/Servora/pull/28 — **merged**. Added
  `scripts/check_classifier.py` for manual real-key verification (same
  pattern as `scripts/check_llm.py`). The existing end-to-end chat test
  now mocks `classify()` so CI stays network-free — worth remembering
  for issue #5 (tool-calling) and the P1 specialist agents: each one
  that starts calling the real LLM will need the same treatment (mock it
  in `test_health.py`'s end-to-end test, add its own unit tests with a
  mocked `call_llm`).
- **New issue #30** — "[Design] Marketing landing page — visual identity
  inspired by AWS Connect Customer"
  (https://github.com/Deekshith2205/Servora/issues/30). A teammate is
  building the frontend visual design (via Antigravity). Scoped to
  borrow *layout patterns only* from the reference page — original copy,
  no fabricated stats/testimonials/awards, since this is a hackathon
  project with no real customers. **No dependency on any backend issue —
  can run fully in parallel.**
- The team merged **issue #5** ("Real tool-calling") and **issue #23**
  ("Deployment readiness") independently in parallel — `call_llm()` now
  supports a full Anthropic tool-calling loop (`app/tools/tool_registry.py`
  builds the schemas/handlers), and `CONTRIBUTING.md`/`README.md` got a
  proper prerequisites/setup rewrite (Python 3.12, Node 22 pinned — matches
  CI). Specialist agents (`app/agents/specialists.py`) are **not yet**
  wired to use tool-calling — that's still each specialist's own issue
  (#6-#9).
- **Issue #4** ("[P0] Implement Planner/Orchestrator routing") implemented:
  `plan()` now calls the real LLM, weighing ticket history + urgency +
  fixability (not sentiment alone) to decide resolve/clarify/escalate.
  **Contract change**: `plan()` now takes `(classification, customer_id,
  db)` instead of just `(classification)` — `orchestrator.py` updated.
  PR: https://github.com/Deekshith2205/Servora/pull/34 — **merged**.
  Added `scripts/check_planner.py`.
- **Issue #6** ("[P1] Implement Billing specialist agent") implemented:
  `resolve_billing()` runs a real tool-calling loop (order lookup → KB
  policy check → `issue_refund`), never calling the refund tool
  speculatively. Added `_run_specialist()` in `specialists.py` — a small
  shared helper the remaining specialist issues (#7-#9) reused — and
  `_estimate_confidence()` (0.9 action taken / 0.6 grounded-only / 0.2 no
  tools used), the signal Verification consumes. `call_llm()` gained an
  optional `tool_call_log` param (purely additive) to back
  `SpecialistResponse.used_tools`. PR #36 — **merged**.

### 2026-09-13 — P1 complete (#7-#11), one real bug found and fixed

All six P1 issues are now implemented (five in one session, on top of #6
from the day before):

- **#7/#8/#9** (Technical/Order/Account specialists) — bundled into one
  PR since all three just add a system prompt + a one-line
  `resolve_x()`, reusing `_run_specialist()` from #6 untouched. Technical
  grounds in `search_kb` (low-but-not-zero confidence on no KB match, per
  the issue — a lookup was still attempted). Order proactively checks the
  delay policy and offers the courtesy discount without a tool to
  actually issue one (the reply states eligibility, never claims the
  discount was applied). Account is read-only, refuses anything
  account-modifying since no such tool exists. PR:
  https://github.com/Deekshith2205/Servora/pull/39 — open.
- **#10** (Verification Agent) — two deterministic checks, no second LLM
  call: a confidence threshold (0.5), and a narrow "completed-action"
  phrase check that catches a reply claiming "I've issued a refund" when
  `issue_refund` was never actually called. Documented as an
  approximation (a real semantic/second-LLM-judge check would catch
  more) rather than silently overclaiming what it does. First P1 issue
  that needed **no** real-API-key verification at all — `verify()` never
  touches the LLM. PR: https://github.com/Deekshith2205/Servora/pull/40
  — open.
- **#11** (customer memory write/merge) — new `CustomerMemory` DB table
  (one row per customer, a flat JSON fact list), real
  `load_profile`/`merge_profile`/`extract_facts` in `memory.py`, and a
  **new orchestrator step** (nothing called `memory.py` at all before
  this) after a successful resolution — wrapped in try/except so a
  failed extraction never breaks the customer's response. **Contract
  change**: both memory functions gained a `db: Session` param;
  `planner.py` and `specialists.py::_run_specialist` updated. PR:
  https://github.com/Deekshith2205/Servora/pull/41 — open.

  **Real bug found and fixed alongside #11** (not originally in scope,
  but the fix touched the exact same code path): `_run_specialist()`
  never actually told the model the customer's ID — every specialist
  tool call needing one (`get_customer_orders`, `get_customer`, ...) was
  relying on the model to guess it. This had gone completely unnoticed
  because **no session working on issues #2 through #11 has ever run
  any of this against a real Anthropic API key** — every test mocks the
  Anthropic client, which correctly proves the *plumbing* works but
  can't catch "the model has no way to know this fact." Fixed by
  including `"Customer ID: {id}"` in every specialist's message content
  (the known-profile-facts context from #11 goes in right alongside it).

### 2026-09-13 (continued) — P2 complete (#12-#14), a SECOND real bug found

All three P2 issues implemented, stacked #12 → #13 → #14 (each branched
on top of the previous, since each literally builds on what the last
one produced):

- **#12** (Escalation Agent) — `build_handoff_packet()` makes one LLM
  call to produce situation/root_cause_hypothesis/recommended_action;
  `attempted_fixes`/`urgency` are passed straight through by the caller.
  `ChatResult` gained a `handoff_packet` field. Scope call: this agent
  doesn't re-decide resolve-vs-escalate (Planner/Verification already
  did) — cites `verification.CONFIDENCE_THRESHOLD` (made public for
  this) instead of duplicating it. PR:
  https://github.com/Deekshith2205/Servora/pull/43 — open.
- **#13** (expose the packet via the API) — `ChatResponse` gained
  `handoff_packet`; `CustomerChat.jsx` renders a real handoff card on
  escalation instead of the generic text. PR:
  https://github.com/Deekshith2205/Servora/pull/44 — open.
- **#14** (Staff Dashboard detail) — **`/api/chat` never created or
  touched a `Ticket` row before this** — the dashboard's queue only ever
  showed seeded demo data. `Ticket` gained `trace_json`/
  `handoff_packet_json`; every escalation now persists a real ticket;
  new `GET /api/escalations/{id}`; `StaffDashboard.jsx` click-to-expand
  detail view. PR: https://github.com/Deekshith2205/Servora/pull/45 —
  open.

  **A second real bug, found the same way as #11's**: writing #14's
  tests (the first ones needing *real* seeded DB data through a bare
  `TestClient(app)`) revealed that a bare `TestClient(app)` — used at
  module level in `test_health.py`/`test_tickets_api.py` — does **not**
  reliably trigger FastAPI's ASGI lifespan (`create_all()` +
  `seed_if_empty()`) in this environment. Every earlier test avoided
  this by mocking every DB-touching agent, or building its own isolated
  in-memory engine. Fixed with `tests/conftest.py` (a `pytest_configure`
  hook that creates+seeds the schema once, unconditionally). **Unlike
  #11's bug, a real API key would NOT have caught this one** — it's a
  test-infrastructure gap, not an LLM-behavior gap. Worth remembering:
  "mock everything LLM-related" hides more than one kind of blind spot.

### 2026-09-13 (continued) — everything above merged; teammate redesign + P3 started, verified live

All of #39, #40, #41, #43, #44, #45, and #46 are now **merged**. On top
of that, while this session was focused on backend agent work, a
teammate (via Antigravity) delivered far more than issue #30's original
scope:

- **Issue #30 landing page** — done well beyond spec: a real hero,
  stat-free "how it works" pipeline diagram matching the actual agent
  graph, honest customer/staff feature sections using real product
  screenshots, real resource links, a genuine FAQ, and — correctly — **no
  fabricated stats, testimonials, or awards** anywhere. Routes to the
  real app at `/app`. Verified live in-browser, not just reviewed as a
  diff.
- **The redesign went far past the landing page** — the whole app shell
  (sidebar nav, icons), Customer Chat, Staff Dashboard, and Analytics all
  got a full visual + UX pass across several commits
  (`fe70a77`, `b56433d`, `2655962`, `d8eb1a0`). This landed *concurrently*
  with this session's P2 work on the same files (`CustomerChat.jsx`,
  `StaffDashboard.jsx`, `App.css`) — the teammate/merger already resolved
  that conflict directly on the design branch (commit `2c358fb`, "fix:
  resolve main merge conflicts in marketing UI") before merging PR #38.
  Verified live: the #14 escalation-detail feature (click a ticket → see
  trace/handoff packet, or the "predates the pipeline" fallback for
  seeded tickets) still works correctly inside the redesigned dashboard.
- **Issue #15** (root-cause clustering across tickets, P3) is also
  **already merged** (PR #47) — deterministic clustering (shared
  category + theme, or ≥2 shared meaningful tokens) over open tickets
  from the last 30 days, connected-components grouping, a
  root-cause-hypothesis string per cluster. `Analytics.jsx` now renders
  real cluster cards instead of the stub. **P3 is already partway done
  without this session doing it.**
- **Found while verifying all this live** (not a code bug, a dev-workflow
  footgun): `Base.metadata.create_all()` does not retroactively add new
  columns to an existing SQLite table. A `servora.db` created before a
  schema change (e.g. #14's `trace_json`/`handoff_packet_json`) will
  throw `OperationalError: no such column` until the file is deleted and
  reseeded. Worth a `CONTRIBUTING.md` note: *"pulled changes that touch
  `models.py`? Delete `backend/servora.db` before restarting."* Not done
  yet — flagging here so it isn't lost.
- Also found live: an **unhandled backend exception currently produces a
  bare "Failed to fetch" in the browser**, not a readable error — FastAPI's
  default handler for an uncaught exception bypasses `CORSMiddleware`
  entirely, so the browser can't read the response at all. Affects any
  unhandled error, not just the missing-API-key case. A global exception
  handler that still emits CORS headers would fix this for good. Not
  done yet.

### 2026-09-13 (continued) — P3 complete (#16, #17): a THIRD real bug found, this one live in the browser

- **#16** (analytics dashboard beyond clustering) implemented:
  `compute_churn_signals()` (per-customer escalation-count buckets —
  medium ≥2, high ≥4 — over the trailing window) and `compute_trend()`
  (daily ticket-volume counts) added to `app/api/analytics.py`;
  `analytics_summary()`'s response gained `churn_signals`/`trend` keys.
  `Analytics.jsx` renders a Ticket Volume Trend bar chart and a Churn
  Risk table. 10 new backend tests. PR:
  https://github.com/Deekshith2205/Servora/pull/49 — **merged**.

  **A CSS bug found live, not in tests**: the trend chart's bars
  (flex-item `div`s with an inline `height`) rendered at 0px despite a
  correct inline style, no overriding CSS rule (checked via
  `document.styleSheets`), and a correctly-sized flex container —
  root cause never fully isolated. Fixed by switching the bars to SVG
  `<rect>` elements (geometry, not CSS layout) — rendered correctly on
  the first try. Worth remembering: a flex-item's inline `height` is
  not always trustworthy for a data viz; SVG sidesteps the whole class
  of layout bug.

- **#17** (Learning Agent — draft KB updates from resolved escalations)
  implemented: `app/agents/learning.py::draft_kb_article()` (structured
  output: should_add + title/body/tags, from category/customer
  message/resolution notes/handoff-packet context);
  `POST /api/escalations/{id}/resolve` marks the ticket resolved then
  best-effort drafts a KB suggestion (`except LLMError: pass` — a
  drafting failure never blocks resolving the ticket itself); new
  `app/api/kb.py` router for listing/approving KB articles;
  `StaffDashboard.jsx`'s escalation drawer gained a Resolution section
  (notes → Mark Resolved → KB suggestion card with Approve/Dismiss, or
  a "no suggestion" message). PR:
  https://github.com/Deekshith2205/Servora/pull/50 — **merged**.

  **A third real bug, and the first one caught live in the browser
  rather than by writing a test carefully**: `llm.py` swallowed a bare
  `TypeError`. With zero Anthropic credentials resolvable at all (no
  API key, no `ant auth login` profile — **the default state of every
  dev/demo environment used on this project so far**), the SDK's own
  `_validate_headers` raises a plain `TypeError`, not an `anthropic.*`
  exception — none of `call_llm()`'s except clauses caught it, so it
  propagated as an unhandled 500 instead of becoming an `LLMError`.
  This silently broke the "best-effort, must not break the main
  request" guarantee for *every* such caller in the codebase (memory
  extraction #11, escalation packets #12, and now KB drafts #17)
  whenever no API key was configured — i.e. every time anyone has run
  this app locally without their own key. Caught by clicking "Mark
  Resolved" in the actual running app and seeing a bare "Failed to
  fetch," then reading the backend logs. Fixed with
  `except LLMError: raise` (don't double-wrap an already-well-formed
  one) followed by a final `except Exception: raise LLMError(...)`
  catch-all; two new tests in `test_llm.py`. **This is the CORS/opaque-
  exception gap flagged (not fixed) in the previous entry, but for the
  specific exception type — the general FastAPI/CORS interaction for
  *other* unhandled exceptions is still open, see below.**

  Two more bugs found live in the same verification pass, both in
  `StaffDashboard.jsx`: (a) a resolved ticket's `kb_suggestion: null`
  (the Learning Agent legitimately declining to suggest anything — the
  exact case the bug above produces) was indistinguishable from "not
  resolved in this session," so it silently fell through to the wrong
  UI message — fixed with an explicit `justResolved` flag; (b)
  resolving a ticket patched its status into the local list in place
  instead of removing it, leaving a stale "Resolved" row (and inflated
  total count) until the next reload, even though the code's own
  comment said it shouldn't — `GET /api/escalations` only ever returns
  open/escalated tickets, so the list now filters the resolved ticket
  out locally to match.

  Also fixed (infrastructure, not agent behavior): the same test-DB-
  pollution class of bug as #14, but for test-to-test isolation this
  time rather than lifespan — several test files call `SessionLocal()`
  directly and mutate the same file-based `servora.db` the dev server
  uses, which actively broke a real test this session (an earlier
  test's cleanup deleted a ticket a later test depended on). Fixed in
  `conftest.py` by pointing `DATABASE_URL` at an isolated temp-file
  SQLite DB before `app.config`/the module-level engine is ever
  imported — verified via `md5sum` that the dev DB is untouched by a
  `pytest` run.

  **P3 is now fully done** (#15, #16, #17 all merged).

### 2026-09-13 (continued) — P4 complete (#18-#21) and P5 complete (#22): all originally-scoped issues now implemented

All four P4 (hotel voice-booking stretch feature) issues plus the one P5
issue are implemented and PR'd, each following the same branch → implement
→ test → PR workflow, stacked in dependency order (#18 → #19, #18 → #20 →
#21; #22 independent, off `main`):

- **#18** (Booking Agent) — `app/tools/booking_tools.py`'s
  `check_availability`/`create_draft_booking` (real overlap-aware
  availability math against `Room.total_count`, never trusting a prior
  claim before actually writing a booking) plus
  `app/agents/booking.py::run_booking_agent()`. **Stateless per call, by
  design**: unlike the support-ticket specialists (one message in, one
  reply out), a booking is a multi-turn slot-filling conversation, so the
  caller (`POST /api/booking`) passes the FULL transcript each turn — the
  same `{role, content}` shape `call_llm` already accepts — rather than
  inventing new server-side "in-progress booking" state. PR:
  https://github.com/Deekshith2205/Servora/pull/51 — **merged** (by the
  team, not this session).

  **Proactive fix, not reactive this time**: applied issue #17's lesson
  (a bare `TypeError` from the Anthropic SDK with no credentials at all
  isn't an `anthropic.*` exception and wasn't converted to `LLMError`)
  *before* hitting it again — `POST /api/booking` explicitly catches
  `LLMError` and returns `HTTPException(502, ...)`, since this endpoint
  has no best-effort degrade path (the reply IS the response). Verified
  live: a clean 502 with a readable detail, not a raw crash.

- **#19** (browser-mic voice I/O) — new "Book a Room" nav tab
  (`BookingChat.jsx`): `SpeechRecognition` for the mic button,
  `SpeechSynthesis` to read replies aloud, both feature-detected (the
  text path always works regardless of browser support). PR:
  https://github.com/Deekshith2205/Servora/pull/52 — open.

  **Real bug found and fixed while wiring this up**: `api/client.js`'s
  shared `request()` helper discarded a failed response's JSON `detail`
  field in favor of a bare `"Request to X failed: 502"` — every endpoint
  that goes out of its way to return a specific, readable error (like
  #18's booking-chat 502 above) was having that message silently thrown
  away before a user ever saw it. Fixed to surface `detail` when present.
  Verified live: with no API key configured, the chat now shows the real
  "Anthropic API key is missing or invalid..." message instead of a bare
  status code; also confirmed the in-pane mic-permission-denied path
  degrades gracefully (clear message, button returns to idle, doesn't
  stick on "Listening…").

- **#20** (staff booking review/edit UI) — new "Bookings" section in the
  Staff Dashboard (`BookingsPanel.jsx`) + `app/api/bookings.py`
  (`GET`/`PATCH /bookings/{id}`, `POST /bookings/{id}/confirm`),
  completing `docs/ARCHITECTURE.md`'s `AI_DRAFTED → STAFF_REVIEWED →
  CONFIRMED` state machine. `Booking` gained `edit_log_json` (a flat
  `{field, old_value, new_value, at}` list — only fields that actually
  changed get logged, no phantom "changed from X to X" entries) and an
  `edit_log` property so Pydantic's `from_attributes` mode can read it
  directly. PR: https://github.com/Deekshith2205/Servora/pull/53 — open.

  Verified live end-to-end against the real dev DB (no LLM involved, so
  no API-key dependency): seeded a booking directly, confirmed it
  through the UI, then edited a second one and confirmed the drawer's
  "Edit history" rendered the diff correctly.

- **#21** (customer notification on booking edit) — new
  `app/services/notifications.py`: `build_booking_edit_diff_message()`
  composes a plain-language diff from one PATCH's new log entries;
  `notify_customer_of_booking_edit()` records it as a new `Notification`
  row (`GET /api/notifications` to list them), wired into `#20`'s
  `update_booking()` so every real edit produces one. PR:
  https://github.com/Deekshith2205/Servora/pull/54 — open.

  **A deliberate, explicitly-documented deviation from the issue
  text**: NOT a real email/SMS send, despite the issue suggesting "the
  Gmail connector already available in this workspace" — that connector
  belongs to the chat session that built the feature, not to the
  deployed FastAPI app, which would need its own Gmail OAuth
  credentials/consent flow to send mail as part of its own runtime
  behavior. A recorded, queryable `Notification` row matches this
  codebase's existing convention for every other external dependency
  (`mock_tools.py` mocks orders/refunds/room lookups too) — real
  provider integration is a self-contained follow-up. Verified live:
  edited a booking's guest count through the actual UI, saw the exact
  diff message in a new "Customer notified" section, confirmed the
  `Notification` row via `GET /api/notifications` independently.

  **P4 is now fully implemented** (all four issues; #18 merged, #19/#20/
  #21 open as PRs from this session).

- **#22** (richer seed data + demo script), the one P5 issue — added a
  "Bluetooth Speaker" order and two prior *resolved* "package never
  arrived" tickets for Alice, and wrote `docs/DEMO_SCRIPT.md` covering
  the exact message to type for each of the 3 required scenarios
  (autonomous resolve, multi-step investigation + action, escalation
  with full handoff). **Built deliberately around Alice
  (`customer_id=1`), not Bob**: `CustomerChat.jsx`/`BookingChat.jsx` both
  hardcode `DEMO_CUSTOMER_ID = 1`, so every scenario reachable through
  the actual UI has to be something she can trigger — Bob's existing
  duplicate-charge ticket isn't demoable live as the UI stands today.
  PR: https://github.com/Deekshith2205/Servora/pull/55 — **merged**.

  **P4 and P5 are now both fully merged** — every issue from the
  original 22-issue backlog (#2-#22) is done. PR #53 needed a small
  merge-conflict resolution against `main` first (both #52 and #53 had
  independently added new functions to `frontend/src/api/client.js`
  right after the same shared fix — purely additive, no real conflict,
  just kept both sides' new exports).

### 2026-09-13 (continued) — a new [P6] tier opened: 7 issues, rescoped from 10 pasted descriptions that predated most of this backlog

A teammate pasted 10 fresh-looking issue descriptions ("Implement Intent
Classification", "planner.py is a stub", "Implement memory.py", ...) that
turned out to describe work already merged across P0-P3 — the wording
reads like it was written before any of that landed. Rather than post
them verbatim (which would have looked like asking the team to rebuild
already-shipped agents), each was checked against the actual current
code first, and only genuine gaps became new issues — 7 of the original
10 had a real, specific gap; the other 3 (planner reasoning/trace,
customer memory, confidence-based escalation) are already substantially
done and got no new issue:

- **#57** — Classifier has no `confidence` field anywhere, and no
  fallback if the LLM call fails (`classify()` just propagates
  `LLMError`, unlike `_update_memory()`'s already-established
  best-effort pattern).
- **#58** — `orchestrator.py` only ever persists a `Ticket` row on
  escalation (`_create_escalation_ticket()`); a *resolved* conversation's
  trace is returned once in the API response and then gone. Blocks real
  resolution-rate/escalation-rate analytics (#62) from having a
  meaningful denominator.
- **#59** — Billing agent has no data model for "duplicate charge" or
  "paid but never fulfilled" — it just trusts the customer's claim today.
- **#60** — Order agent has no data model for cancellation or inventory
  shortfall — `Order.status` only covers
  `processing|shipped|delivered|refunded`.
- **#61** — The "investigation timeline" is a single expand/collapse
  toggle over a flat list (`InvestigationPanel` in `CustomerChat.jsx`,
  the drawer's own trace rendering in `StaffDashboard.jsx`), not a real
  per-step vertical timeline.
- **#62** — Analytics has clustering/churn/trend (#15/#16) but not
  resolution rate, escalation rate, sentiment trend, or confidence
  distribution — the last one depends on #57, the first two on #58.
- **#63** — The escalation drawer shows only a bare `customer_id`, no
  profile or ticket history; only "Resolve" exists, no reassign/close.
  Reassign is scoped down to a free-text `assigned_to` field rather than
  real staff accounts, since there's no auth system in this codebase at
  all yet — flagged rather than quietly assumed away.

Labeled **[P6]** (not real GitHub labels, matching the existing `[P0]`-
`[P5]` title-prefix convention — see Key decisions above for why) since
they're hardening/enhancement work on top of an already-complete
original backlog, not new foundational scope.

**Update: #57-#63 are now all implemented and merged** (moved fast —
see `docs/ARCHITECTURE.md`'s per-issue sections for #58/#59/#60/#62/#63;
the entries above describing them as newly-opened are left as-is since
they're an accurate record of that moment, not stale in a way worth
rewriting).

### 2026-09-13 (continued) — [P6] Enforce specialist-specific tool permissions

Closed a real security gap: every specialist (`resolve_billing/technical/
order/account`) called the generic `build_tool_registry(db)` and
received the FULL 8-tool set — including `issue_refund` — with only each
specialist's system prompt instructing it which tools it should use. A
prompt is not an authorization boundary.

- `app/tools/tool_registry.py`: added
  `SPECIALIST_TOOL_PERMISSIONS` (the one authoritative specialist →
  allowed-tools mapping — adjusted from a first-draft version to match
  what each specialist's *current* prompt actually calls and what tools
  actually exist today, not copied blindly) and
  `build_filtered_tool_registry(db, specialist)`, which filters the
  generic registry's schemas AND handlers down to just that specialist's
  allowlist. The generic `build_tool_registry(db)` is unchanged —
  `scripts/check_tool_calling.py` and `tests/test_tools.py` still use it
  directly.
- `app/agents/specialists.py`: `_run_specialist()` gained one new
  keyword-only param, `specialist: str`, to select the allowlist — the
  only contract change needed. All four public `resolve_x()` signatures
  are untouched.
- Enforcement is real at both levels: the LLM never sees a schema for a
  tool outside its allowlist (tool exposure), and even if a tool_use
  block names an unauthorized tool anyway, it isn't a key in that
  specialist's filtered handler dict — `call_llm()`'s existing "unknown
  tool" rejection (from issue #5, already tested) handles it, reused
  rather than duplicated.
- `tests/test_tool_permissions.py` (new, 11 tests): each specialist's
  exact allowed set; the actual kwargs a mocked Anthropic client
  receives per specialist (proving the LLM itself never sees an
  unauthorized schema); an end-to-end defensive-execution test scripting
  a fake model attempting `issue_refund` as the Account specialist and
  confirming the seeded order's DB row is untouched; a control-case test
  proving the identical tool_use block DOES execute when sent through
  the (authorized) Billing registry, to rule out "the handler was just
  broken" as an alternative explanation.
- `tests/test_order_issues.py` needed two one-line updates (its two
  direct `_run_specialist(...)` calls now pass `specialist="order"`) —
  the only pre-existing test file touched.

Full suite: **196 passed** (185 pre-existing + 11 new), including the
issue's specifically-named regression targets
(`test_specialists.py`/`test_billing.py`/`test_order_issues.py`/
`test_tools.py`, 63 tests, run in isolation as well as part of the full
suite). Frontend lint/build: clean (no API/contract surface changed by
this issue at all — purely an internal backend security boundary, so no
live browser verification was needed here the way a new endpoint or UI
change would call for).

## Next up (in priority order)

1. **Still the single highest-priority loose thread, now spanning the
   ENTIRE backlog.** Nobody has confirmed `call_llm()` against a real
   Anthropic API key. Real bugs have repeatedly been found without one —
   missing customer ID (#11), a TestClient lifespan gap (#14), the
   bare-`TypeError`/CORS-opaque-error gap (#17) — a real key might still
   find something categorically different (actual model behavior,
   which nothing here can substitute for). Also the only way to actually
   run `docs/DEMO_SCRIPT.md`'s 3 scenarios for real.
2. New [P6] backlog (#57-#63) — #57 (classifier confidence) and #58
   (persist resolved-ticket trace) are worth doing first since #62
   (analytics) and part of #59/#60's detection work depend on data those
   two issues add.
3. Two small, well-scoped fixes identified previously, still not done:
   (a) a `CONTRIBUTING.md` note about deleting `servora.db` after a
   schema change (`create_all()` doesn't migrate existing SQLite
   tables — hit repeatedly again this session, once per new
   migration-touching PR), (b) a **general** FastAPI exception handler
   so an unhandled error of any kind still carries CORS headers back to
   the browser — #17 fixed one specific exception *type*, not the
   general gap.
4. Optional, not blocking a demo: wire up a real Gmail/SMS provider
   behind `app/services/notifications.py` (see #21's entry above for
   why it's mocked today) — self-contained, doesn't change any caller.

## Open questions / blockers

- **`call_llm()` has never been confirmed against a real Anthropic API
  key, by any session, across the entire backlog.** This has already
  caused several real, independently-discovered bugs (missing customer
  ID in #11; the TestClient lifespan gap in #14; the bare-`TypeError`
  gap in #17). Top priority — see Next up #1.
- **CI is not a required check yet.** Someone with admin access on
  github.com/Deekshith2205/Servora needs to go to Settings → Branches →
  add a branch protection rule on `main` → require the CI status checks
  before merging. Nobody in any session so far has had admin rights to
  do it directly.
- **General unhandled-exception → CORS gap still open** (only the one
  specific `TypeError` case was fixed in #17) — see Next up #3(b).
- **`servora.db` schema drift after `create_all()` still requires a
  manual delete** — see Next up #3(a).
- **No staff-identity/auth system exists at all** — flagged concretely
  while scoping #63 (reassign needs *someone* to reassign to). Worth a
  real decision (even a fake/demo login) before #63 is picked up, rather
  than each future issue re-discovering the same gap.
