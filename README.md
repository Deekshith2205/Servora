# Servora

Autonomous AI customer support system — understands customer intent,
investigates issues across multiple data sources, takes real actions, and
escalates complex cases to a human agent with complete context.

Built for the "Customer Support" hackathon track. Judged on **context
retention, reasoning, automation, and human handoff** — not just
question-answering. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for
the full agent graph and design rationale.

## Stack

- **Backend**: FastAPI + SQLAlchemy (SQLite for the demo) + an LLM
  (Anthropic by default, swappable) — `backend/`
- **Frontend**: React + Vite — `frontend/`. Views: Customer Chat, Staff
  Dashboard, Book a Room (voice/text hotel-booking stretch feature),
  Analytics, and the **Investigation Board** — a dedicated page showing
  the full autonomous reasoning chain (agent activity feed, timeline,
  evidence, root cause, resolution, and cross-conversation agent
  performance metrics) behind every conversation, backed by
  `Investigation`/`InvestigationStep` records persisted alongside every
  `/api/chat` call. See `docs/ARCHITECTURE.md`'s "Investigation Board"
  section.

## Status

This is the **base scaffold**. The agent pipeline (classify → plan →
specialist → verify → escalate) runs end-to-end today, but every agent is
a stub that returns a placeholder. Real behavior is being built one GitHub
issue at a time — see the repo's Issues tab, prioritized P0 (foundation)
through P4 (stretch features). Pick one up; see
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the workflow.

## Quick start

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for full prerequisites and setup details.

```bash
# Terminal 1 — backend (Python 3.12)
cd backend
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # set ANTHROPIC_API_KEY for live AI chat
uvicorn app.main:app --reload

# Terminal 2 — frontend (Node 22)
cd frontend
cp .env.example .env
npm ci
npm run dev
```

Frontend: **http://localhost:5173** · Backend: **http://localhost:8000**
