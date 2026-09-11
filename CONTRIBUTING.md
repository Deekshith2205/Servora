# Contributing to Servora

1. Pick an open issue (they're prioritized — start at P0 if you're not sure
   what to take, since later issues depend on earlier ones).
2. Branch off `main`: `git checkout -b issue-<number>-short-name`.
3. Keep changes scoped to the issue. If you find yourself needing to change
   a shared contract (an agent's return shape, an API route's schema),
   flag it in the issue/PR description — several other issues depend on
   what's already there.
4. Open a PR into `main` referencing the issue (`Closes #<number>`).
5. Backend: run `pytest` from `backend/` before opening the PR.
   Frontend: run `npm run build` from `frontend/` before opening the PR.
   (CI runs both automatically on every PR — see below — but running them
   locally first gives you faster feedback than waiting on CI.)

## CI

Every PR automatically runs `.github/workflows/ci.yml`: backend `pytest`
and frontend `npm run build`. Check the PR page for the status — a red
check means something's broken, don't merge until it's green (or you
understand why it's failing). CI runs with no `ANTHROPIC_API_KEY`, so
never write a test that requires a real key — `scripts/check_llm.py` is
the manual, real-key smoke test and intentionally isn't part of the
suite.

## Running locally

**Backend**
```bash
cd backend
python -m venv .venv
./.venv/Scripts/activate   # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env        # fill in your own LLM API key
uvicorn app.main:app --reload
```

**Frontend**
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Backend runs on `http://localhost:8000`, frontend on `http://localhost:5173`.
