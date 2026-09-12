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

## Next up (in priority order)

1. **Still outstanding**: verify `call_llm()` against a real API key
   (`scripts/check_llm.py` and `scripts/check_classifier.py`) — merged
   twice now without that confirmation ever happening.
2. Issue #4 — Planner/Orchestrator routing (depends on #3, merged).
3. Issue #5 — real tool-calling for specialists (depends on #2, merged;
   can run in parallel with #4).
4. Then the P1 specialist agents (#6–#9) can be split across teammates in
   parallel — each only touches its own function in
   `app/agents/specialists.py`.
5. Issue #30 (landing page design) — separate track, in parallel with all
   of the above, whenever the teammate doing frontend visual design picks
   it up.

## Open questions / blockers

- **`call_llm()` has never been confirmed against a real Anthropic API
  key**, by any session, across both #2 and #3. Everything is verified
  by mocked/offline tests only so far. High priority to close before more
  agents are built on top of it — see Next up #1.
- **CI is not a required check yet.** Someone with admin access on
  github.com/Deekshith2205/Servora needs to go to Settings → Branches →
  add a branch protection rule on `main` → require the CI status checks
  before merging. Nobody in any session so far has had admin rights to
  do it directly.
