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

### 2026-09-13 (continued) — [FEATURE] AI Investigation Board & Autonomous Reasoning Timeline

New dedicated frontend page (`InvestigationBoard.jsx`, its own nav tab)
showing the full autonomous reasoning chain behind every conversation —
was previously only a collapsible panel next to a chat bubble or inside
the Staff Dashboard drawer.

- `app/db/models.py`: new `Investigation` + `InvestigationStep` tables —
  ADDITIVE alongside `Ticket.trace_json` (issue #14), not a replacement;
  see the ARCHITECTURE.md section for why a normalized table (real
  `GROUP BY agent_name` for "Agent Performance Metrics") rather than
  parsing JSON blobs harder.
- `app/agents/specialists.py`: every tool call now captures a real,
  human-readable evidence string (`_describe_evidence()`, derived from
  the actual `Order`/`Customer`/`KBArticle` objects mock_tools.py
  returns — never placeholder text). `SpecialistResponse` gained one
  additive `evidence: list[str]` field.
- `app/orchestrator.py`: `handle_message()` times each stage and records
  a parallel `step_records` list; `_persist_investigation()` writes it
  at every point the function already returns (both escalation paths,
  the resolved path) — mirrors `_create_ticket()`'s call sites exactly.
- `app/api/investigations.py` (new): `GET /api/investigations` (list),
  `GET /api/investigations/{id}` / `.../by-ticket/{ticket_id}` (full
  detail), `GET /api/investigations/metrics/agents` (cross-investigation
  aggregate).

**Real bug found wiring this up**: `ChatResult.ticket_id` has existed
since issue #14, but `POST /api/chat`'s response schema never actually
included it — the frontend had no way to link a finished conversation to
its ticket (or now, Investigation) without a fragile separate lookup.
Fixed by adding `ticket_id` to `ChatResponse` (additive/optional).

**Honest architectural call, documented rather than glossed over**:
`/api/chat` is fully synchronous — there's no genuine in-progress
streaming state to subscribe to. The Board fetches an already-complete
investigation and replays its real steps with a staggered reveal
animation instead of pretending to be truly live via SSE/WebSocket
(a legitimate, larger follow-up if genuinely real-time updates are
wanted). The four "bonus, if feasible" items from the original request
(agent swarm visualization, a dependency graph, a distinct replay mode)
were intentionally not built — out of scope for the core deliverable.

Verified live with a real Gemini call end-to-end, using the issue's own
example message ("Payment deducted but order not created"): a real
Investigation was persisted with genuine per-step durations (1945ms/
1108ms/1273ms), real evidence, a real root cause and resolution, and the
Board rendered every section (A-G plus Agent Performance Metrics)
correctly against that live data — not a mock. Full backend suite: **204
passed** (196 pre-existing + 8 new). Frontend lint/build: clean.

### 2026-09-13 (continued) — [SWARM] 12 new issues opened: Agent Swarm Visualization batch, gap-checked against the real pipeline first

A hackathon-judging pass asked for an "Agent Swarm Visualization System" —
before opening anything, checked the request's example flow (Billing Agent
+ Order Agent investigating in parallel, plus separate Knowledge/Resolution
agents) against the actual code: Planner routes to exactly ONE specialist
per ticket, sequentially; `search_kb` is a tool call inside a specialist,
not its own agent; resolution text comes from the specialist itself. That
parallel-investigation flow doesn't exist today, so it was filed as its own
explicitly-out-of-scope issue (#88) rather than silently assumed as a
prerequisite. The other 11 issues visualize the REAL graph (Classifier →
Planner → chosen specialist → Verification → Escalation/Memory):

- **#77** [P0, Backend] `InvestigationStep` gains real `started_at`,
  `reasoning_text`, `used_tools_json` — data that's already computed in
  `orchestrator.py`/`specialists.py` today and silently dropped before
  reaching the DB.
- **#78** [P1, Backend] Explicit `depends_on_step_numbers` per step — the
  pipeline's branches (direct-escalate vs. verification-fail-escalate vs.
  resolve) aren't representable by step_number ordering alone.
- **#79** [P2-stretch, Backend] True SSE streaming — replaces the
  Investigation Board's existing "honest limitation" (a staggered replay
  of already-complete data, `/api/chat` being fully synchronous) with
  genuine live push. Recommends the smaller of two designs (client-
  generated stream key alongside the existing synchronous call) rather
  than a bigger job-queue rewrite.
- **#80** [P1, Backend] `graph` field (nodes+edges) added to the existing
  `InvestigationOut` — deliberately NOT four new endpoints as the original
  request implied, since three of those would just duplicate
  `/api/investigations/{id}`.
- **#81** [P0, Frontend] New Agent Swarm Network page — node/edge diagram,
  the one visualization Servora doesn't have at all today (explicitly cut
  from the original Investigation Board's scope as a "bonus, if
  feasible" item).
- **#82** [P0, Frontend] Shared expandable agent-card component (reasoning
  + evidence + tools + outputs) — reused by both the new Swarm view and
  retrofitted into the existing Board's checklist.
- **#83** [P1, Frontend] Idle/Running/Waiting/Completed/Failed status —
  ships a v1 against replay timing now; `Waiting` explicitly deferred
  until #79 exists rather than faked.
- **#84** [P1, Frontend] Swarm execution-order timeline strip (a third,
  Gantt-style view distinct from the network graph and the existing
  checklist).
- **#85** [P2-stretch, Frontend] Live-mode/replay-speed toggle — has no
  real content until #79 ships.
- **#86** [P0, Integration] One explicit test matrix proving #77/#78's new
  fields are populated *correctly per branch* at all three of
  `orchestrator.py`'s return points — this codebase's track record shows
  multi-call-site changes reliably miss one path on the first pass.
- **#87** [P1, Integration] Live-key verification pass + a Swarm-specific
  `docs/DEMO_SCRIPT.md` addition, done last — explicitly reuses (doesn't
  duplicate) the long-standing real-API-key-verification blocker already
  tracked below.
- **#88** [P3, out-of-scope flag] Genuine parallel multi-specialist
  investigation, filed separately as agent-architecture work, not a
  visualization task — not part of the current push.

No code changed yet — issues only, per the session's own instruction to
analyze and scope before implementing.

### 2026-09-13 (continued) — [EXPLAIN] 11 new issues opened: Explainable AI Panel batch

Same gap-check-first approach as the [SWARM] batch: checked the request's
example ("Billing policy section **4.2**" as a citation) against
`KBArticle` (title/body/tags only, no section granularity) before writing
anything — flagged as an explicit, documented scope limit in #91 rather
than silently promising sub-article citations the KB model can't back.
Also found and flagged (not yet fixed) a real display bug while scoping
#93: `InvestigationTimeline.jsx` (the customer-chat trace view) matches
agent labels/icons against the literal string `"specialist"`, which never
equals a real `agent_name` like `"billing_specialist"` — every specialist
step has silently been falling through to the generic fallback icon/label.
Scheduled to be fixed as part of #93 rather than patched in isolation.

- **#89** [P0, Backend] Planner gains `alternatives_considered` — the
  resolve/clarify/escalate space already maps cleanly onto the requested
  "Escalate to human / Request clarification / Auto refund" example.
- **#90** [P0, Backend] Per-agent confidence breakdown — pure aggregation,
  `InvestigationStep.confidence` already exists per step today.
- **#91** [P0, Backend] Structured `evidence_refs`/`policy_references`
  (typed, id-addressable) alongside the existing prose `evidence` list —
  KB citation is whole-article only, documented as a scope limit.
- **#92** [P1, Backend] `/explanation`, `/evidence`, `/confidence` endpoints
  under `app/api/explanations.py`, built on the existing
  Investigation/InvestigationStep tables (no new storage) — includes a
  deterministically-composed `decision_rationale` (explicitly NOT a new
  LLM call).
- **#93** [P0, Frontend] Shared `ExplainableAIPanel.jsx` ("Why did Servora
  recommend this?"), compact mode for Customer Chat + full mode for the
  Staff Dashboard drawer — one component, not two divergent ones. Fixes
  the agent-label bug above along the way.
- **#94** [P0, Frontend] Large confidence gauge + per-agent breakdown bars.
- **#95** [P1, Frontend] Evidence Explorer + Policy References (clickable,
  reuses the existing KB router from issue #17 rather than a new viewer).
- **#96** [P1, Frontend] Alternative Actions Considered section.
- **#97** [P1, Frontend] Decision Tree visualization — deliberately kept
  distinct from the Swarm batch's execution graph (#81): one shows what
  ran, this shows what else could have run.
- **#98** [P0, Integration] Cross-branch consistency test matrix (same
  pattern as the Swarm batch's #86) — new fields must degrade honestly on
  branches where they don't apply (e.g. no specialist confidence on a
  direct-Planner escalation), never show a fake value.
- **#99** [P1, Integration] Wire the panel into both real call sites +
  demo script. Explicitly notes two of the original "bonus" asks
  ("interactive reasoning graph," "decision replay") are already the
  Swarm batch's #81/#85 — flagged so they don't get rebuilt twice under
  different names.

No code changed yet — issues only.

### 2026-09-13 (continued) — All 10 [SWARM]/[EXPLAIN] P0 issues implemented, tested, and verified LIVE against a real Gemini call

Two stacked PRs, backend first (frontend branched off it, not off `main`,
since the frontend genuinely needs the new API fields to render anything
real):

- **PR #100** (`p0-swarm-explain-backend`) — closes #77, #80, #86, #89,
  #90, #91, #92, #98. `InvestigationStep` gained `started_at`,
  `reasoning_text`, `used_tools_json`, `alternatives_json`,
  `evidence_refs_json` (all additive). Planner's `PlanDecision` gained
  `alternatives_considered` from the same structured-output LLM call — no
  second call. Specialists' `SpecialistResponse` gained structured
  `evidence_refs`. `orchestrator.py`'s `_record()`/`_persist_investigation()`
  thread all of this through at all 3 pipeline branches. New
  `app/api/explanations.py` (`/explanation`, `/evidence`, `/confidence`),
  and `GET /api/investigations/{id}` gained a `graph` field — both P1
  issues (#80, #92) done alongside the P0s since the P0 frontend has
  nothing real to render without them. **#78's explicit
  `depends_on_step_numbers` column was deliberately NOT added** — the
  pipeline never fans out yet, so edges are correctly derivable from step
  order alone (documented in `GraphEdgeOut`'s docstring); revisit only if
  #78's future fan-out scenario actually gets built. 8 new tests
  (`tests/test_explainability.py`), full suite 212 passed.
- **PR #101** (`p0-swarm-explain-frontend`, based on #100) — closes #81,
  #82, #93, #94. New shared `agentMeta.jsx` (agent label/icon/confidence-
  tier helpers) extracted from `InvestigationBoard.jsx`. **Fixed the
  `InvestigationTimeline.jsx` bug flagged when #89-#99 were scoped**: it
  matched agent icons/labels against the literal string `"specialist"`,
  which never equals a real `agent_name` — every specialist step was
  silently using the generic fallback. New `AgentDetailCard.jsx` (#82,
  shared), `ConfidenceGauge.jsx` (#94), `ExplainableAIPanel.jsx` (#93,
  compact popover in Customer Chat / full section in the Staff Dashboard
  drawer), and a new "Agent Swarm" page/nav tab (#81) rendering the
  backend's `graph` field as an animated node/edge diagram.

**Verified LIVE end-to-end, not just via mocked tests** — this environment
already had a working `GOOGLE_API_KEY`/`LLM_PROVIDER=gemini` in
`backend/.env`. Ran both dev servers, sent "I was charged twice for my
order" as the real demo customer through the actual browser: a genuine
duplicate-payment refund was investigated and resolved, the Agent Swarm
graph rendered the real 5-step topology with real per-agent timing, the
Explainable AI Panel showed a real 90% confidence gauge with a real
per-agent breakdown (Classifier 98%, Billing 90%) — and, importantly,
**two real `alternatives_considered` entries** ("Clarify" and "Escalate,"
each with a specific real rejection reason), confirming the nested
Pydantic structured-output schema (#89's biggest open risk, never
confirmed against a real provider before this) actually works. No
console errors. `InvestigationBoard.jsx` re-verified live with zero
regressions from the `agentMeta.jsx` extraction.

**Important precision, not to overclaim**: this confirms the **Gemini**
path end-to-end for the first time on this project. The long-standing
Open Questions item below is specifically about the **Anthropic** key/
model path (`claude-opus-5` via `anthropic==1.5.0`) — that one specific
gap is still open; a nested-schema call like `alternatives_considered`
hasn't been confirmed against Anthropic's `messages.parse` yet, only
Gemini's `response_schema`.

### 2026-09-13 (continued) — #96 and #99 solved; a real PR-sequencing gap found and fixed

- **#96** (Alternative Actions Considered — chosen action visually
  distinct) — `ExplanationOut` gained `chosen_action`
  (`app/api/explanations.py::_chosen_action()`), parsed deterministically
  from the planner step's own code-controlled action-label text (never
  raw LLM prose) rather than adding a redundant column. Frontend: a
  "Chosen" badge above the rejected alternatives, which now render struck
  through.
- **#99** (wire the panel + demo script) — the panel was already wired
  into both Customer Chat and the Staff Dashboard drawer as of #101;
  this added the missing `docs/DEMO_SCRIPT.md` walkthrough.

**A real gap found while pushing this work, not a code bug but a process
one**: PR #100 (base `main`) had already been merged, but PR #101 (base
`p0-swarm-explain-backend`, i.e. stacked on #100 rather than on `main`)
had been merged into *that branch*, not into `main` — so all of #101's
frontend work (the Agent Swarm view, the Explainable AI Panel, the
`InvestigationTimeline.jsx` bug fix) was sitting on a branch, invisible
from `main`, discovered only by diffing `origin/main..p0-swarm-explain-
backend` before pushing #96/#99's commits. Fixed by opening **PR #102**
(`p0-swarm-explain-backend` → `main`) carrying the missing frontend work
plus #96/#99. **Until #102 is merged, `main` does NOT have the Agent
Swarm tab, the Explainable AI Panel, or the ExplainableAIPanel/
AgentSwarmView components at all** — worth remembering if a fresh clone
of `main` looks like it's missing the whole batch.

Re-verified LIVE against a real Gemini call (see full details in PR
#102's description) on BOTH branches this time — a resolved case (showed
"CHOSEN: resolve") and, on a second run with richer seeded ticket
history, a direct-Planner escalation (showed "CHOSEN: escalate" with
real rejection reasons for the other two actions) — confirming the
chosen/alternatives split degrades correctly on the branch that skips the
specialist entirely, not just the happy path. `pytest`: 212 passed.
`npm run lint`/`build`: clean.

### 2026-09-13 (continued) — all 9 remaining [SWARM]/[EXPLAIN] issues done: #78, #83, #84, #95, #97, #79, #85, #87, plus #99/#96's manual-close cleanup

Three more stacked PRs, in priority order, each built on the previous:

- **PR #103** (`p1-swarm-status-timeline-graph`, base `main`) — closes
  #78, #83, #84. `InvestigationStep` gained `depends_on_json`, set
  explicitly per step in `orchestrator.py` rather than the graph API
  assuming step order implies dependency (`investigations.py::
  _build_graph()` now reads it directly). Real Idle/Running/Completed/
  Failed status vocabulary in the Agent Swarm view — "Waiting"
  intentionally omitted until real streaming existed (see #79 below).
  New Swarm Timeline strip (Gantt-style, real duration_ms widths).
- **PR #104** (`p1-evidence-explorer-decision-tree`, base #103) — closes
  #95, #97. New `app/api/records.py` (`GET /api/records/orders|customers|
  tickets/{id}`, deliberately NOT under `/api/orders` etc. — `/api/
  tickets/{id}` would have collided with the existing literal
  `GET /api/tickets/resolved`) plus `GET /api/kb-articles/{id}`, backing
  a real clickable Evidence Explorer instead of plain text. New
  `DecisionTree.jsx` — the Planner's real branch point plus a Verification
  pass/fail branch when a specialist ran; deliberately distinct from the
  Swarm execution graph (that shows what ran, this shows what else could
  have). **Found while building it**: `orchestrator.py` doesn't actually
  special-case "clarify" differently from "resolve" — both hit the same
  code path — the tree says so via an inline caption instead of drawing a
  fictional distinct flow. **A real pre-existing test-isolation bug found
  and fixed**: several test files (`test_analytics.py`, `test_kb_api.py`)
  delete all `Ticket` rows on the same shared file-based test DB
  `conftest.py` uses for the whole session; since SQLite reuses low
  ROWIDs once a table empties, a plain autoincrement insert in a new test
  could collide with a `ticket_id` an earlier test's `Investigation` row
  (UNIQUE) already claims — order-dependent, and it actually fired once
  new tests shifted the row count. Fixed with an explicit out-of-range id
  for the one new test that needed to insert a `Ticket`.
- **PR #105** (`p2-live-streaming-swarm`, base #104) — closes #79, #85,
  #87. The big one: `app/services/stream_bus.py` (new) — a plain
  thread-safe `queue.Queue`-per-`stream_key` pub/sub (not `asyncio.Queue`:
  `handle_message()` runs in FastAPI's sync-endpoint worker thread, not
  the event loop). `POST /api/chat` gained an optional `stream_key`
  (client-generated UUID); `orchestrator.py::handle_message()` publishes
  one real event per stage AS it completes when given one, wrapped in
  `try/finally` so the stream always closes even if an LLMError
  propagates. New `GET /api/investigations/stream/{stream_key}` (SSE, hand-
  rolled `text/event-stream` — no new dependency) with a keepalive/idle-
  timeout so an orphaned key can't leak a queue+connection forever.
  Frontend: `liveInvestigation.js` (new) — a tiny cross-page singleton so
  Customer Chat (which starts a stream) and the Agent Swarm view (a
  different page/component tree) agree on the one in-flight investigation
  without threading a React Context through `App.jsx`. Customer Chat's
  "Investigating…" placeholder now shows real agent names arriving live.
  Agent Swarm gained a genuine LIVE mode (nodes appear as real SSE events
  arrive, no timer) distinct from REPLAY mode (now with a 0.5x/1x/2x/
  Instant speed control, since it's honestly labeled as a replay).

  **A real bug found and fixed while live-testing this**:
  `AgentSwarmView.jsx` unmounts/remounts every time the user switches
  tabs (`App.jsx` swaps `<ActiveComponent />`), but `subscribeLive()` only
  pushed FUTURE state changes to a new subscriber — a component mounting
  after `startLive()` had already fired (exactly the "switch to Agent
  Swarm mid-investigation" demo path) started from `null` and never
  learned a stream was active until its next event, missing an
  already-in-progress or already-finished investigation entirely. Fixed
  by having `subscribeLive()` push the current value immediately on
  subscribe (a standard "push current value" pub-sub pattern) — verified
  fixed by reproducing the exact failure live, then confirming the retry
  auto-selected the just-finished investigation correctly on every
  subsequent attempt.

  **Honest limitation, not glossed over**: this session verified real-time
  streaming directly (Customer Chat's own "Investigating…" indicator
  showed real agent names — Classifier, Planner, Account, Verification —
  appearing progressively DURING a real Gemini call, confirmed via
  repeated live captures) and verified the LIVE→completed hand-off logic
  is correct and consistent (5-for-5 across different messages/step
  counts, the just-finished investigation was always auto-selected
  correctly in the Agent Swarm view). What was NOT captured in this
  session: a screenshot of the Agent Swarm tab's red LIVE badge itself
  mid-flight — this demo customer's seeded ticket history makes most
  scenarios resolve/escalate in as little as 3-4 seconds, faster than
  this session's browser-automation round-trip could reliably win the
  race. The underlying mechanism is verified correct by direct evidence
  and code review; only that one specific screenshot is missing. `docs/
  DEMO_SCRIPT.md` was updated with a timing note about this for whoever
  runs the real demo.

  Full backend suite: **222 passed** (219 + 3 new in
  `tests/test_streaming.py`). `npm run lint`/`build`: clean throughout.

**Also cleaned up while pushing this work**: issues #99 and #96 had
actually already been solved (merged via PR #102) but stayed open on
GitHub — `Closes #96, #99` in a PR body apparently only auto-links the
first issue in a comma-separated list. The same problem was found to have
silently left 10 more already-merged issues open (#80, #82, #86, #89,
#90, #91, #92, #93, #94, #98) — all now closed manually with a comment
pointing at the actual merging PR. **Worth remembering for every future
PR in this repo**: write `Closes #N` on its own line per issue, never a
comma-separated list, and don't trust a closed-issue count to mean
"nothing was missed" without spot-checking.

**Every issue from both the [SWARM] and [EXPLAIN] batches is now done**
except the one deliberately-out-of-scope issue: #88 (parallel
multi-specialist investigation — a real agent-architecture change, not a
visualization task, filed as its own future consideration rather than
quietly built or quietly dropped).

### 2026-09-13 (continued) — #88 built too: genuine parallel multi-specialist investigation

The user explicitly asked for #88 despite it having been flagged
out-of-scope — confirmed first (full implementation, not a stub), then
built as **PR #106** (`p2-parallel-multi-specialist`, base
`p2-live-streaming-swarm` — merge #103 → #104 → #105 → #106 in order).

- `planner.py`: `PlanDecision`/`_PlanSchema` gain `additional_agents` —
  the LLM names OTHER specialists (besides `target_agent`) that should
  ALSO investigate, only for a genuinely cross-cutting issue (empty in
  the common case).
- `orchestrator.py`: when `additional_agents` is non-empty, every named
  specialist runs **concurrently** via `ThreadPoolExecutor` — each on its
  **own** `SessionLocal()` (`_run_specialist_isolated()`), never the
  request's shared `db` session, since SQLAlchemy `Session`s aren't safe
  for concurrent cross-thread use. `database.py`'s SQLite `connect_args`
  gained a `timeout` for the same reason (two threads could now
  legitimately contend for SQLite's write lock at once — its default is
  to fail immediately rather than wait). Each specialist gets its own
  `InvestigationStep`, all depending on the SAME planner step (fan-out,
  using #78's `depends_on` override mechanism — `_record()` gained a
  `depends_on` param for exactly this). `_reconcile_specialist_responses()`
  then deterministically combines their replies (clearly labeled per
  specialist, no synthesis LLM call) into one response — confidence is
  the **minimum** across specialists (conservative, matching
  Verification's existing philosophy), evidence/tools are the union — and
  records one more step, "reconciliation," depending on ALL the
  specialist steps (fan-in). Verification/Escalation/Memory downstream
  are completely unchanged — they just see one `SpecialistResponse`,
  same as always.
- Frontend: `AgentSwarmView.jsx`'s graph rendering was reworked from a
  flat left-to-right row to a real **layered/columned layout**
  (`computeLayers()`) — nodes at the same dependency depth render as a
  vertical stack in one column (with a red "PARALLEL" badge when >1),
  connected by curved SVG paths computed from the actual `depends_on`/
  `graph.edges` data, not an index-to-index assumption. Live mode's SSE
  step events now carry `depends_on` too (`orchestrator.py`'s stream
  payload), so a live fan-out renders correctly in real time, not just on
  replay.

**Verified LIVE against a real Gemini call using the issue's own example
message** ("Payment deducted but order not created"): the Planner
genuinely set `target_agent=order` (or billing) with the other as an
additional agent, both specialists ran and independently found/refunded
real payment-fulfillment mismatches on two different orders, the
Investigation timeline showed both specialist steps plus a
"Reconciliation" step, and the Agent Swarm graph rendered exactly the
intended shape: Classifier → Planner → **[Billing Agent, Order Agent]**
(one column, PARALLEL badge, real curved fan-out/fan-in lines) →
Reconciliation → Verification → Memory. Confidence correctly showed the
lower of the two specialists' (60% vs. 90%). Clicking each parallel node
showed its own independent reasoning/tools/evidence. No console errors.

2 new tests (`tests/test_parallel_specialists.py`): the cross-cutting
case (fan-out/fan-in dependencies, reconciled reply, min-confidence) and
a regression test proving the single-specialist path is byte-for-byte
unaffected. Full backend suite: **224 passed** (222 + 2 new). `npm run
lint`/`build`: clean.

**Every issue from both the [SWARM] and [EXPLAIN] batches is now
implemented**, including the one originally flagged out-of-scope.

### 2026-09-13 (continued) — merge-tracking cleanup: #83/#84 closed manually, #88's code landed on `main` via PR #107

`main` was checked directly rather than trusted from memory: PRs #103,
#104, and #105 were ALL already merged (someone merged the stack
correctly this time — #104/#105/#106 landing into each other's branches,
then #103's branch merge brought the whole chain into `main` in one
commit). Only **one commit was still missing from `main`**: #106's
[SWARM] #88 work, which had merged into its base branch
(`p2-live-streaming-swarm`) rather than `main` — the exact same gap
PR #102 fixed once before. Opened **PR #107** to land it; CI green.

Also found: PR #103's body used `Closes #78, #83, #84.` on one line —
the same comma-list mistake flagged earlier in this log slipped through
again on this one PR. Only #78 auto-closed. #83 and #84 were both
genuinely done (merged, on `main`) but stayed open on GitHub — closed
manually with comments pointing at PR #103.

**Standing lesson, worth repeating since it recurred even after being
documented once**: always write one `Closes #N` per line, and after any
multi-PR push, verify against `main` directly (`git log
origin/main..origin/<branch>`, or check specific files exist via `git
show origin/main:<path>`) rather than trusting that "the PR merged" means
"the code is on `main`" — a stacked PR can merge successfully into a
non-`main` base and look identical to a real merge in `gh pr list`.

### 2026-09-13 (continued) — [CRITIC] Critic Agent: independent review of root cause, evidence, and resolution (#108-#113)

New backlog, built on the same branch as #88 (`p2-parallel-multi-
specialist`, on top of the not-yet-merged #107): a genuine second LLM
opinion on a specialist's finding, closing the exact gap
`verification.py`'s own docstring named as future hardening ("a real
semantic/second-LLM-judge pass would catch more... not done here").

- **#108** (Database) — `InvestigationStep` gains `critic_review_json`
  (nullable, a single object unlike every other `*_json` column here) +
  a `critic_review` property, populated only on the critic's own step.
- **#109** (Backend) — new `app/agents/critic.py::critique()`: one
  structured-output LLM call reviewing root_cause + resolution +
  evidence, returning `agrees`/`confidence`/`alternative_hypothesis`/
  `reasoning`. Deliberately does NOT see the specialist's own confidence
  score, so it can't defer to a number instead of actually reviewing.
  Advisory only — a fail-safe default (`agrees=True`, confidence 0.0,
  reasoning noting the failure) on any `LLMError`, same spirit as
  `classifier.py`'s deterministic fallback.
- **#110** (Backend/Integration) — wired into `orchestrator.py` right
  after the specialist (or, for #88's fan-out, the reconciliation) step:
  one new "critic" `InvestigationStep`. **A real design subtlety, not
  glossed over**: inserting a step between the specialist and Verification
  meant Verification's *default* dependency (issue #78's "depends on the
  immediately preceding step") would have silently pointed at the new
  critic step instead of the specialist it actually reviews — `verify()`
  never sees the critic's opinion, only `response`. Fixed with an
  explicit `depends_on` override on Verification's own `_record()` call,
  so both Critic and Verification now correctly branch directly off the
  specialist/reconciliation step (a small diamond shape, not a flattened
  chain). Explicitly does NOT change Verification's approve/reject
  decision — advisory, not a gate, by design.
- **#111** (API) — `critic_review` surfaced on `InvestigationStepOut`,
  riding through the existing `GET /api/investigations/{id}` response
  (no new endpoint), same convention `alternatives_considered` already
  established for the planner.
- **#112** (Frontend) — new "Critic Review — Independent Second Opinion"
  card in `InvestigationBoard.jsx`, right after the Resolution card:
  Agree/Disagree badge, confidence, reasoning, and (only when
  disagreeing) the Alternative Hypothesis. **Agent Performance Metrics
  picked up "Critic" as a tracked agent for free** — it's the same
  cross-investigation `GROUP BY` every other agent already flows through,
  no new dashboard code needed — direct proof the "reuse existing
  storage" requirement actually held.
- **#113** (Testing) — `tests/test_critic.py` (6 new unit tests) found
  **two real bugs** before they shipped: `critique()`'s alternative-
  hypothesis normalization was backwards (`if result.agrees is False else
  (x or None)` doesn't clear `alternative_hypothesis` when the model
  contradictorily agrees AND fills the field — fixed to `if not
  result.agrees else None`); and the original confidence-clamp test
  couldn't even be written the naive way, since `_CriticSchema`'s own
  `ge=0.0, le=1.0` already rejects an out-of-range value at construction
  — fixed by using `_CriticSchema.model_construct()` to bypass validation
  the same way a genuinely non-conformant provider response theoretically
  could. Every existing resolve-path test across 6 other files
  (`test_health.py`, `test_investigation.py`, `test_investigations_api.py`,
  `test_orchestrator.py`, `test_parallel_specialists.py`,
  `test_explainability.py`, `test_streaming.py`) needed a `critique` mock
  added (same "any future real-LLM-calling agent needs the same
  treatment" note `test_health.py` already carried) plus updated
  exact-sequence/depends_on assertions now that "critic" is a real step.

**Verified LIVE against real Gemini calls, twice**: a direct-Planner
escalation (no specialist ran — critic correctly never ran either, no
Critic step in the trace) and a resolved technical-support case, where
the Critic Review card rendered a genuine, specific critique ("The
resolution to escalate to a human specialist is a reasonable and safe
response when documentation is missing, especially for a VIP tier
customer" — citing real evidence, not a generic verdict) with real 95%
confidence, and Agent Performance Metrics correctly showed "Critic" as a
newly-tracked agent. No console errors either run.

Full backend suite: **231 passed** (224 + 7 new: 6 in `test_critic.py`,
1 API round-trip test). `npm run lint`/`build`: clean.

### 2026-09-13 (continued) — same merge-target gap recurred a third time: PR #115 lands the Critic Agent on `main`

PR #107 merged `p2-parallel-multi-specialist` into `main`. PR #114 then
merged `p3-critic-agent` (the Critic Agent work) into
`p2-parallel-multi-specialist` — its base branch, not `main` — the exact
same recurring gap, now a third time despite being documented twice
already. Caught the same way: checked `git log
origin/main..origin/p2-parallel-multi-specialist` directly rather than
trusting `gh pr list`'s MERGED status, found the 2 missing commits,
opened **PR #115** to land them. CI green (both checks pass).

**This has now recurred three times** (#101→#102, #106→#107, #114→#115)
despite the standing lesson already being written down after the first
one. Worth being explicit about the actual root cause: a stacked PR
whose base is a feature branch (not `main`) will show as `MERGED` in
every listing exactly like a normal merge — there is no different status
for "merged into a dead-end branch." The only way to know for certain
`main` has what a PR claims to close is a direct diff/file check against
`origin/main`, not the PR's own merged/closed state. Do this check after
*every* stacked-PR merge from now on, not just when something seems off.

**Update**: PR #115 has since merged — confirmed via
`git log origin/main..origin/p2-parallel-multi-specialist` (empty) and
`git branch -r --contains <tip commit>` showing `origin/main`. The
Critic Agent (#108-#113) is genuinely on `main` now; "Next up" item 0
below is done.

### 2026-09-13 (continued) — Agent Collaboration Graph: the static Agent
Swarm view is now a real React Flow graph

Implemented the user's "Agent Collaboration Graph" task in full — see
PR #116: https://github.com/Deekshith2205/Servora/pull/116 (base
`main`, branched from the confirmed post-#115 tip, CI green on both
checks). Replaced `AgentSwarmView.jsx`'s hand-drawn SVG graph
(`GraphNode`/`computeLayers`/`ConnectorSVG`/`SwarmGraph`) with
React Flow (`@xyflow/react`), reusing the exact same depth/column
algorithm and every existing data field (`graph`/`timeline`,
`depends_on`, `confidence`, `duration_ms`, `evidence`) — no backend or
schema change at all.

Three new files carry all the new logic:
`frontend/src/utils/investigationToFlow.js` (mapping layer — investigation
records → React Flow nodes/edges, adds an `agentType()` classifier and
a new **"escalated"** status the old vocabulary didn't have),
`frontend/src/components/AgentNode.jsx` (custom node — icon/name/type/
status/confidence/duration/evidence count), and
`frontend/src/components/AgentCollaborationGraph.jsx` (the React Flow
wrapper — zoom/pan/fit-to-view, animated edges, loading/empty states).
`AgentSwarmView.jsx` itself needed only its graph-rendering code
removed and one component swapped in; all state, live-SSE growth,
replay speed control, and the Swarm Timeline strip are untouched.

Two real bugs found via live verification against the real Gemini key
(not just build/lint): (1) `liveGraph` can briefly go `null` while
`isLive` is still true, because `CustomerChat.jsx`'s `clearLive()` can
fire before `AgentSwarmView`'s own "investigation finished" effect
switches away from LIVE mode — fixed with a null guard; (2) a genuine
CSS Grid overflow bug: `.swarm-detail-panel` (a grid item) had the
browser-default `min-width: auto`, so the graph's own content forced
the grid track wider than the viewport at narrow widths, rendering the
whole graph visually blank/off-screen on mobile — fixed with the
standard `min-width: 0`. Verified live: the full 8-step parallel
fan-out/fan-in shape (with a real Critic node) and a separate 3-step
escalation-only chain (no critic step, "Escalated" status showing
correctly) both render correctly; node click still opens
`AgentDetailCard`; mobile width (375px) reflows correctly after the
CSS fix.

### 2026-09-13 (continued) — [Explainability] Drill-Down Panel: the
Investigation Board's evidence goes from plain text to a real drawer

10 new issues opened (#118-#127, epic #117) then fully implemented —
see PR #128: https://github.com/Deekshith2205/Servora/pull/128 (base
`main`, CI green, not yet merged). Click any evidence item on the
Investigation Board -> a right-side drawer opens with 6 sections
(summary, source record, tool execution, agent reasoning, confidence
breakdown, investigation impact).

Turned out to be mostly wiring, not new capability: [EXPLAIN] #91/#95
already added structured `evidence_refs` (`{type, ref_id, label}`) and
a record-lookup API (`/api/records/...`), but only
`ExplainableAIPanel.jsx`'s Evidence Explorer ever used them — the
Investigation Board still rendered the old plain-text `evidence`
prose list. This PR extends that existing machinery rather than
building a second evidence pipeline.

New backend endpoint `GET /api/investigations/{id}/evidence/{evidenceId}`
(`explanations.py`, same "derived, not stored, no new LLM call"
family as `/explanation`) — `evidenceId` is `"{step_number}:{index}"`,
addressing one `evidence_refs` entry without any schema change.
Deliberately does NOT re-embed the source record itself (that's what
`/api/records/...`/`/api/kb-articles/{id}` are for) — the frontend
reuses those exact fetchers. Returns a deterministic 3-part confidence
breakdown (evidence quality / data freshness / source reliability,
each formula documented inline) and a step-level-attributed,
deduplicated tool list (a step can legitimately call `search_kb` 2-3
times with different queries — listing it 2-3 times with identical
stats was pure noise and would have collided as a React key).
`CustomerProfileOut` gained 2 additive fields
(`previous_tickets_count`, `risk_level`) reusing `analytics.py`'s
existing churn thresholds rather than new magic numbers.

**Honesty over fabrication, again**: no "Account Status" field
anywhere (not a real concept in this schema — `tier` is the closest
real analog); the Order Record card shows only real fields, not the
original spec mockup's invented Carrier/Last Location/Last Updated.

**A real bug found via live verification**: the new drawer's overlay
initially copied the existing `.app-drawer-overlay` pattern
(`position: absolute`) — but since `.app-main` (its positioned
ancestor) is itself the scrolling element, that anchors the overlay to
the scrolled CONTENT offset, not the viewport. Opening the drawer
while scrolled down rendered it far off-screen above (confirmed via
`getBoundingClientRect()`: `top: -1267px`). Fixed with
`position: fixed`. **Worth flagging**: the pre-existing
`.app-drawer-overlay` (Staff Dashboard's Escalation Drawer) likely has
this exact same bug and hasn't been checked — not fixed here since
it's out of this PR's scope, but a real, findable issue for later.

Verified live against the real #88 fan-out investigation's 30+
`evidence_refs`: real source records (including the new
`previous_tickets_count=7`/`risk_level=high` on the seeded VIP
customer), deduplicated tools, real reasoning/confidence-breakdown/
impact text, working timeline-strip navigation between evidence items,
Escape/backdrop close, and the exact spec'd drawer widths confirmed at
each breakpoint (480px desktop / 420px tablet / full-screen mobile,
each measured directly via `getBoundingClientRect()`, not just eyeballed).
Backend: 240 passed, 1 skipped, +12 new tests. `npm run lint`/`build`: clean.

### 2026-09-13 (continued) — PR #128 merged to `main`; general
unhandled-exception → CORS handler closes a long-standing open question

**PR #128 merge**: verified branch/PR state, base, and clean working
tree first; merged via `gh pr merge 128 --merge` (commit `99f569a1`);
pulled `origin/main`; confirmed via both
`git log origin/main..origin/p4-explainability-drilldown` (empty) and
`git merge-base --is-ancestor` that nothing was left unmerged; spot-
checked a specific file directly against `origin/main`. Full backend
suite (240 passed, 1 skipped) and frontend lint/build re-run clean on
the merged code, then verified live in a real browser against the
actual merged `main` — real evidence-drawer data confirmed one more
time, no console errors. **Found and fixed a small real gap**: 10 of
the 11 tracking issues (#117-#126) auto-closed on merge, but #127
("Documentation") didn't — its `Closes #127` line had been left out of
the PR body — closed manually with an accurate comment (also noting
`docs/DEMO_SCRIPT.md` was never actually updated in that PR, only
`CLAUDE.md` + inline docstrings were).

**General FastAPI exception handler** (PR #129,
https://github.com/Deekshith2205/Servora/pull/129, CI green, not yet
merged): closes the general unhandled-exception/CORS gap this log has
flagged since issue #17 (which only fixed ONE specific exception type
in `llm.py`). A single `@app.exception_handler(Exception)` in
`app/main.py` — preserves existing `HTTPException`/
`RequestValidationError` behavior untouched (Starlette always prefers
the most specific handler by MRO), logs the real exception+traceback
server-side, returns only a generic `{"detail": "..."}` to the client.

**A real Starlette mechanic found while building this, not assumed**:
a handler registered for the base `Exception` type is invoked by the
*outermost* `ServerErrorMiddleware` (see Starlette's own
`build_middleware_stack()`), which sits **outside** `CORSMiddleware`
and sends its response via the raw ASGI `send` it was originally given
— so simply registering the handler does **not**, by itself, add CORS
headers. Confirmed empirically (a first-pass test failed: 500 with no
`Access-Control-Allow-Origin` header at all) before fixing it by
manually adding the same header `CORSMiddleware` would have, replicating
its exact current single-origin configuration. Worth remembering for
any future Starlette/FastAPI exception-handling work in this repo — the
naive "just register `@app.exception_handler(Exception)`" answer that's
all over blog posts/StackOverflow is incomplete for a CORS-enabled app.

Live-verified properly rather than assumed: temporarily added a
debug-only route raising a real exception, drove it from the actual
frontend origin via browser `fetch()` (not curl — curl can't prove the
browser's own CORS check passes), confirmed no "blocked by CORS policy"
console error and a clean (not CORS-blocked) network entry, then fully
removed the debug route (confirmed via `git diff`) before committing.
6 new tests (`tests/test_error_handling.py`) — including a real
Starlette/TestClient nuance documented there: `ServerErrorMiddleware`
re-raises the original exception after sending the response (by
design, so a real server still logs it), which needs
`TestClient(app, raise_server_exceptions=False)` for the specific tests
that intentionally trigger this path. Full suite: 246 passed (240 + 6
new), 1 skipped. Backend-only change — no frontend files touched.

**Update**: PR #129 has since merged directly to `main` (confirmed via
`git log origin/main -1`) — the general CORS/opaque-error gap is fully
closed, on `main`, not just in a branch.

### 2026-09-15 — Real Shopify integration: Order/Billing agents can
investigate a connected real store

New backlog item, implemented directly (not issue-tracked — see
PR #130: https://github.com/Deekshith2205/Servora/pull/130, base
`main`, CI green, not yet merged). Servora can now investigate real
customer orders from a connected Shopify store, alongside (never
replacing) the existing mock data — the architecture (Classifier ->
Planner -> Specialists -> Critic -> Verification -> Escalation/Memory)
is completely unchanged; this only adds a new integration settings
surface, a new service layer, and 3 new permission-gated tools.

New `ShopifyIntegration` table + Settings -> Integrations page +
`GET/POST /api/integrations/shopify/status|connect|disconnect` —
`connect` verifies real credentials against Shopify's own `/shop.json`
before ever persisting as "connected"; the access token is never
returned by any read endpoint, and `disconnect` clears it entirely
(not just a status flag). New `app/services/shopify_service.py` — real
Admin **REST** API calls (deliberately not GraphQL: REST's integer
`id`s fit the existing `EvidenceRefOut.ref_id: int` with zero schema
changes), real retries (429 honoring `Retry-After`, 5xx, network
errors), real auth/timeouts. `search_orders()` is honest about a real
REST limitation (no generic full-text query param exists) rather than
inventing one that doesn't. 3 new tools
(`lookup_shopify_order`/`_customer`/`_fulfillment`), permission-gated
to Billing + Order only via the existing `SPECIALIST_TOOL_PERMISSIONS`
mechanism — no Shopify write tool exists at all. A real evidence_ref
type (`shopify_order`/`shopify_customer`) rides through the exact same
`evidence_refs` pipeline every other tool already writes to — appears
automatically in the Investigation Board, Evidence Explorer, and
Explainable AI Panel with zero new evidence-system code.

**Verified live, not just unit-tested**: stood up a throwaway local
mock Shopify server + one temporary, clearly-marked line pointing the
real HTTP client at it, fully reverted before committing (confirmed via
`git diff`). Connected a real-shaped store through the actual
Integrations page (real credential round-trip), then asked Customer
Chat about a Shopify order — Billing AND Order specialists ran in
parallel (the existing #88 fan-out), BOTH independently called the real
Shopify tools and cited the real returned data in their replies. Traced
the resulting evidence through the Evidence Explorer (real live-fetched
inline preview), the Investigation Board's evidence grid, the
Explainability drill-down drawer, and the Agent Collaboration Graph
(full real 8-node fan-out/fan-in render).

**A real bug found live**: two specialists independently producing the
identical `shopify_order` evidence ref (a correct outcome of the
parallel architecture, not a bug in the pipeline itself) caused a React
duplicate-key warning in `EvidenceExplorer.jsx` — that component had no
dedup step, unlike the newer Explainability drawer's already-correct
`dedupeEvidence()`. Fixed by porting the same logic in.

**Also spotted live, NOT part of this PR, flagged for later**: the
Agent Swarm view's "Agent Performance Metrics" panel showed an agent
literally labeled **"None Agent"** — `agent_name` rendering as a null
value somewhere, most likely in the parallel-specialist reconciliation
path. A real, visible bug (also independently caught reviewing a
pitch-deck screenshot earlier — see that conversation), not yet
root-caused or fixed.

30 new tests (14 in `test_shopify_service.py` using real
`httpx.MockTransport` against the actual retry/auth/error logic; 7 in
`test_integrations_api.py`; 9 in `test_shopify_records_and_evidence.py`
covering the real specialist -> evidence_refs path end-to-end and the
tool-permission boundary). 5 pre-existing tests updated for the
intentional tool-set expansion. Full backend suite: 276 passed (246 +
30 new), 1 skipped. `npm run lint`/`build`: clean.

### 2026-09-15 (continued) — [Omnichannel] Phase 1 started: #132/#133
(Channel model + conversation source tracking)

35 issues (#131 epic + 34 sub-issues, #132-#165) were opened for a full
Omnichannel Customer Support backlog (Live Chat/Email/WhatsApp/
Instagram/Messenger, all routed through the existing Classifier ->
Planner -> Specialists -> Critic -> Verification -> Escalation pipeline,
never a second investigation system). Implemented the first two,
directly on top of the not-yet-merged Shopify branch's tip (not a new
branch yet — see Open questions if this needs splitting out before a
PR):

- **#132** (Channel model) — new `Channel` table in
  `app/db/models.py`: `key`/`display_name`/`status`
  (active|inactive|not_configured)/`config_json`, seeded in
  `app/db/seed.py::seed_if_empty()` with exactly the 5 channels — Live
  Chat seeds `"active"` (it's the one channel with real, working
  transport today), every other channel seeds `"not_configured"`
  (honest, not fabricated as ready). `display_name` deliberately has a
  `default=""` (unlike e.g. `ShopifyIntegration.store_url`, which has
  none) specifically so a bare `Channel(key=...)` never errors —
  matches this table's own acceptance criteria, unlike a required
  credential field where erroring on a missing value is correct.
- **#133** (Conversation source tracking) — `Ticket`/`Investigation`
  both gained `channel_key: str` (default `"live_chat"`, NOT a real FK
  to `Channel.id` — see both docstrings for why: attribution must
  survive even if the Channel table were ever re-seeded).
  `orchestrator.py::handle_message()` gained an optional
  `channel: str = "live_chat"` parameter, threaded into
  `_create_ticket()`/`_persist_investigation()` at all 3 of the
  function's return points (direct-escalate, verification-fail-escalate,
  resolved) — same additive-parameter pattern `stream_key` (issue #79)
  already established. `ChatRequest`/`POST /api/chat` gained the same
  optional `channel` field, passed straight through.

  **No frontend or read-API changes in this pair** — deliberately out of
  scope per how the issues were scoped: #146 (Phase 4) is what exposes
  `channel` on `GET /api/investigations`, and #135/#136+ (rest of Phase
  1/2) are what give Channel status and Ticket/Investigation channel
  data anywhere to actually be read or seen. This pair is foundation
  only.

  10 new tests (`tests/test_channels.py`,
  `tests/test_channel_tracking.py`) — including an explicit regression
  test proving `handle_message()` called with no `channel` argument
  (every pre-#133 caller) still produces a correct `"live_chat"` row,
  and one covering each of the 3 pipeline branches individually (the
  "codebase's track record shows multi-call-site changes reliably miss
  one path" lesson from #86/#98, applied proactively here rather than
  found live). Full backend suite: **286 passed** (276 + 10 new), 1
  skipped.

  **Verified live, not just unit-tested**: found and worked around the
  documented `create_all()`-doesn't-migrate-SQLite gotcha (deleted the
  stale local `servora.db`, let it reseed) before starting the server.
  Confirmed the 5 real seeded channels via a direct DB query, sent a
  real `POST /api/chat` with `"channel": "whatsapp"` through to a real
  LLM call and confirmed the resulting Ticket AND Investigation rows
  both persisted `channel_key="whatsapp"`, then sent a second real call
  with no `channel` field at all and confirmed it correctly defaulted to
  `"live_chat"` — proving the additive/optional contract holds against
  the real running app, not just mocked tests. `GET /api/investigations`
  and `GET /api/tickets/resolved` (pre-existing endpoints, unmodified)
  both still returned real 200s afterward — no accidental regression
  from the new columns.

  **Follow-up in the same session**: 3 more test cases added to close
  real coverage gaps rather than just padding the count —
  `Channel.key` uniqueness (a real DB constraint, `unique=True`, that
  had no test proving it's actually enforced — #135's future
  channel-status API will look rows up by this key, so an unenforced
  duplicate would be a real bug waiting to happen); the [SWARM] #88
  parallel-specialist fan-out path threading `channel` correctly
  through its own `_persist_investigation()` call (a genuinely
  different code path from the 3 already covered — this repo's own
  track record, #86/#98, is multi-branch changes missing exactly one
  path on the first pass); and an explicit test locking in that an
  arbitrary/unrecognized channel string is accepted without validation
  (deliberate — validating against the seeded Channel table is a future
  normalization-layer concern, issue #142, not this issue's job).
  Backend suite: **289 passed** (286 + 3), 1 skipped. Posted a status
  comment on the epic (#131) rather than closing it — only 2 of 34
  sub-issues are done, so the epic itself stays open.

### 2026-09-15 (continued) — PR #166 (#132/#133) merged; Phase 1
finished (#134, #135) and all of Phase 3 (#142-#145) implemented

**PR #166 merged to `main`** — confirmed via `git log origin/main -1`
before starting this batch, then branched fresh off the real `main`
tip (`omnichannel-p1-p3-channel-flow`) rather than stacking on the old
branch, avoiding the stacked-PR-merge-target gap this log has hit
several times before.

- **#134** (Message source metadata) — `Investigation` gained
  `channel_metadata_json` (nullable, a single object — `None` for the
  common case, same "no fabricated empty value" convention
  `critic_review_json` already established) + a `channel_metadata`
  property. `handle_message()` gained an optional
  `channel_metadata: dict | None = None`, threaded to
  `_persist_investigation()` at all 3 return points.
  `InvestigationOut` gained `channel_metadata` (additive); exposed via
  the existing `GET /api/investigations/{id}` — no new endpoint.
- **#135** (Channel status management) — new `app/api/channels.py`:
  `GET /api/channels` (list all 5 with real status),
  `PATCH /api/channels/{id}` (toggle status — a real 400, not a silent
  no-op, if something tries to activate a channel still
  `not_configured`). New `ChannelOut`/`UpdateChannelStatusRequest`
  schemas; router registered in `main.py`.
- **#142** (Message normalization layer) — new
  `app/services/channel_adapters.py`, the architectural core of the
  whole epic: `normalize_whatsapp/instagram/messenger/email()` (one
  function per channel, each documented against a realistic real
  webhook payload shape for that channel — WhatsApp Cloud API,
  Meta Messaging Platform, a generic inbound-email-parse shape) plus
  `route_channel_message(db, channel_key, raw_payload, stream_key=None)`
  — the ONE caller of `orchestrator.handle_message()` for every
  non-Live-Chat channel, same function `POST /api/chat` already calls.
  `_resolve_or_create_customer()` resolves by email (natural fit for
  the email channel) or phone (WhatsApp) or, for Instagram/Messenger
  (which provide no phone/email at all, only an opaque platform-scoped
  sender ID), a synthesized `{channel}+{external_id}@channel.local`
  placeholder — an honest, documented scope limit rather than
  inventing a real identity `Customer` doesn't model today.
- **#143** (Channel-specific message formatting) — same file:
  `format_reply_for_channel(reply, channel_key)` — strips markdown via
  plain regex substitution for WhatsApp/Instagram/Messenger (no
  parser dependency needed for this codebase's own simple
  bold/italic/code/link/bullet patterns), passes Live Chat and email
  through byte-for-byte unchanged. **Deliberately NOT wired into the
  real reply path yet** — proven correct in isolation only; wiring it
  into `handle_message()`'s actual reply is a separate, later issue
  (#151, "Response formatting by channel") per this backlog's own
  dependency graph.
- **#144** (Conversation synchronization) — the real mechanism is
  `_resolve_or_create_customer()` above: reusing the SAME `Customer`
  row across repeated messages on the same real contact is what makes
  cross-turn context "just work" via the EXISTING `CustomerMemory`
  merge (issue #11) — no second continuity mechanism was built, per
  the issue's own explicit scope note. Added
  `find_recent_conversation_on_channel(db, customer_id, channel_key,
  external_conversation_id)` — a read-only lookup (Python-side scan of
  a customer's last 20 investigations on that channel, not a JSON SQL
  query — simple and correct at this scale) for a future Inbox
  (#136+) to group messages into one conversation row. Does not change
  `route_channel_message()`'s own per-call behavior.
- **#145** (Source attribution) — a pure test file
  (`tests/test_channel_source_attribution.py`), no new production
  code: 12 parametrized assertions (4 channels × 3 pipeline branches —
  direct-escalate, verification-fail-escalate, resolved), each
  confirming `Investigation.channel_key`/`channel_metadata` are
  correct at every branch. Same "test every branch explicitly, don't
  assume" lesson issues #86/#98 already established for the [SWARM]/
  [EXPLAIN] batches, applied here proactively.

**Verified live, not just unit-tested**: deleted the dev `servora.db`
again (the new `channel_metadata_json` column hit the same
`create_all()`-doesn't-migrate gotcha, confirmed by first reproducing
the real `OperationalError: no such column` before fixing it — not
just assumed). Called `route_channel_message(db, "whatsapp", {...})`
directly against the real dev DB with a real Gemini call: a genuinely
new `Customer` was synthesized from just a phone number
(`whatsapp+15555559876@channel.local`), the resulting `Ticket`/
`Investigation` both carried `channel_key="whatsapp"`, and
`GET /api/investigations/by-ticket/{id}` correctly returned the real
`channel_metadata` (`external_conversation_id`/`external_contact`)
over HTTP. Confirmed `GET /api/investigations` and
`.../metrics/agents` (pre-existing, unmodified) still return clean
200s.

42 new tests across 5 new files: `test_channel_metadata.py` (5, #134),
`test_channels_api.py` (6, #135), `test_channel_adapters.py` (13,
#142/#144), `test_channel_formatting.py` (6, #143),
`test_channel_source_attribution.py` (12, #145). Full backend suite:
**331 passed** (289 + 42), 1 skipped.

**Omnichannel epic status: 8 of 34 sub-issues done** (#132-#135,
#142-#145 — all of Phase 1 and Phase 3). Phase 2 (Omnichannel Inbox,
#136-#141) is next in dependency order, and is the first phase with
real frontend work.

### 2026-09-16 — PR #167 merged; #146 (Phase 4's first issue) implemented

Confirmed **PR #167 (#134/#135/#142-#145) merged to `main`** before
starting — also found, already merged from elsewhere (not this
session's work), **PR #168** closing **#136** (Unified Inbox page,
Phase 2's first issue). Branched fresh off the real post-both-merges
`main` tip (`omnichannel-p4-channel-in-investigations`).

- **#146** (Channel information in investigations) — `InvestigationOut`
  already had `channel_metadata` (from #134's own work), but neither it
  nor `InvestigationListItemOut` ever exposed the plain `channel` field
  itself — the exact gap #134's own entry flagged as deliberately
  out-of-scope, deferred to this issue. Both schemas gained `channel:
  str = "live_chat"`; `InvestigationListItemOut` also gained
  `channel_metadata` (the issue's own technical requirements ask for
  both fields on both schemas, not just `InvestigationOut`).
  `investigations.py`'s two builder sites
  (`_to_investigation_out()`/`list_investigations()`) populate both
  from the existing `Investigation.channel_key`/`channel_metadata`
  columns — no new DB column, no orchestrator change, purely a read-API
  exposure of data that has existed since #133.

  4 new tests (`tests/test_investigation_channel_field.py`) — including
  one proving the full-detail and list-summary endpoints agree on the
  same investigation's channel (the two builder sites were updated
  consistently, not just one). Full backend suite: **339 passed** (up
  from 331 pre-#167, plus whatever #136 added elsewhere), 1 skipped.

  **Verified live**: a real `POST /api/chat` with `"channel":
  "whatsapp"` through a real LLM call, then confirmed `channel:
  "whatsapp"` on both `GET /api/investigations/by-ticket/{id}` and
  `GET /api/investigations` for the same ticket; confirmed older rows
  (created before #133 even existed) correctly read `"live_chat"`, not
  null, in the same list response.

## Next up (in priority order)

1. **Still the single highest-priority loose thread, now spanning the
   ENTIRE backlog.** Nobody has confirmed `call_llm()` against a real
   Anthropic API key. Real bugs have repeatedly been found without one —
   missing customer ID (#11), a TestClient lifespan gap (#14), the
   bare-`TypeError`/CORS-opaque-error gap (#17) — a real key might still
   find something categorically different (actual model behavior,
   which nothing here can substitute for). Also the only way to actually
   run `docs/DEMO_SCRIPT.md`'s 3 scenarios for real.
2. ~~New [P6] backlog (#57-#63)~~ — done. ~~[SWARM] batch (#77-#88)~~ /
   ~~[EXPLAIN] batch (#89-#99)~~ — **fully done and merged to `main`**
   (PR #103/#104/#105, plus #88 via #107, the Critic Agent via #115, the
   Agent Collaboration Graph via #116, and the Explainability
   Drill-Down Panel via #128). This item's original detailed sequencing
   plan is left out of this entry now that it's obsolete — see the
   2026-09-13 progress-log entries above for the real implementation
   history if needed.
3. ~~Merge PR #129~~ — done, merged directly to `main`. The general
   CORS/opaque-error gap is fully closed.
4. ~~Merge PR #130~~ — done, merged to `main`.
5. **Fix the "None Agent" bug** found live while verifying #130 — Agent
   Performance Metrics shows an agent literally labeled "None Agent"
   (an `agent_name` rendering as null, most likely somewhere in the
   parallel-specialist reconciliation path). Not yet root-caused.
5a. **[Omnichannel]: 9 of 34 sub-issues done and merged to `main`** —
   #132-#135 (Phase 1, PR #166), #142-#145 (Phase 3, PR #167), #146
   (Phase 4's first issue — Channel information in investigations, PR
   TBD this session). **#136** (Unified Inbox page, Phase 2) has also
   been merged (PR #168) — not this session's own work, observed as
   already-landed when this session next touched the repo; its own
   implementation details are not recorded here since this session
   didn't build it. Remaining: #137-#141 (rest of Phase 2), #147-#165
   (rest of Phase 4 through 8). See the 2026-09-15 progress-log entries
   for the full backlog shape and what each session-implemented issue
   actually does.
6. Two small, well-scoped fixes identified previously, still not done:
   (a) a `CONTRIBUTING.md` note about deleting `servora.db` after a
   schema change (`create_all()` doesn't migrate existing SQLite
   tables — hit repeatedly across sessions, once per new migration-
   touching PR), (b) wire up a real Gmail/SMS provider behind
   `app/services/notifications.py` (see #21's entry above for why it's
   mocked today) — self-contained, doesn't change any caller, not
   blocking a demo.

## Open questions / blockers

- **`call_llm()` has never been confirmed against a real Anthropic API
  key, by any session, across the entire backlog.** This has already
  caused several real, independently-discovered bugs (missing customer
  ID in #11; the TestClient lifespan gap in #14; the bare-`TypeError`
  gap in #17). Top priority — see Next up #1. **Update, still precise
  about what this does and doesn't cover**: the 2026-09-13 [SWARM]/
  [EXPLAIN] P0 session verified the **Gemini** path live end-to-end for
  the first time on this project (including a nested structured-output
  schema, `PlanDecision.alternatives_considered`) — that specific class of
  risk is now retired for Gemini. The **Anthropic** key/model path
  (`claude-opus-5`) specifically remains unconfirmed; the same nested-
  schema question is open for `messages.parse` there too.
- **CI is not a required check yet.** Someone with admin access on
  github.com/Deekshith2205/Servora needs to go to Settings → Branches →
  add a branch protection rule on `main` → require the CI status checks
  before merging. Nobody in any session so far has had admin rights to
  do it directly.
- **`servora.db` schema drift after `create_all()` still requires a
  manual delete** — see Next up #6(a).
- **No staff-identity/auth system exists at all** — flagged concretely
  while scoping #63 (reassign needs *someone* to reassign to). Worth a
  real decision (even a fake/demo login) before #63 is picked up, rather
  than each future issue re-discovering the same gap.
- **The "None Agent" display bug** (see the 2026-09-15 Shopify
  integration progress-log entry) — a real agent_name rendering as
  null somewhere, not yet root-caused. See Next up #5.
- **PR #130 (Shopify integration) not yet merged to `main`** — see
  Next up #4.
