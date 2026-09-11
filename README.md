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
- **Frontend**: React + Vite — `frontend/`, three views: Customer Chat,
  Staff Dashboard, Analytics

## Status

This is the **base scaffold**. The agent pipeline (classify → plan →
specialist → verify → escalate) runs end-to-end today, but every agent is
a stub that returns a placeholder. Real behavior is being built one GitHub
issue at a time — see the repo's Issues tab, prioritized P0 (foundation)
through P4 (stretch features). Pick one up; see
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the workflow.

## Quick start

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for full setup. Short version:

```bash
# backend
cd backend && python -m venv .venv && ./.venv/Scripts/activate
pip install -r requirements.txt && cp .env.example .env
uvicorn app.main:app --reload

# frontend (separate terminal)
cd frontend && npm install && cp .env.example .env && npm run dev
```

Open `http://localhost:5173`.
