# Contributing to Servora

## Prerequisites

Make sure these are installed before you start:

| Tool | Required version | Notes |
|------|-----------------|-------|
| Git | any recent | `git --version` |
| Python | **3.12** | Matches CI. Check with `python --version`. |
| Node.js | **22 LTS** | Matches CI. Check with `node --version`. |
| npm | bundled with Node 22 | Check with `npm --version`. |

---

## 1. Clone the repository

```bash
git clone https://github.com/Deekshith2205/Servora.git
cd Servora
```

---

## 2. Backend setup

All commands below are run from the **`backend/`** directory.

```bash
cd backend
```

### Create and activate a virtual environment

**Windows (PowerShell)**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Windows (cmd)**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**macOS / Linux**
```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Create the environment file

```bash
# Windows PowerShell / cmd
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `backend/.env` and set your Anthropic API key if you want real AI responses:

```
ANTHROPIC_API_KEY=sk-ant-...
```

> **Note:** `ANTHROPIC_API_KEY` is only required for the live chat endpoint.
> The backend starts, the database seeds, and the health check works without any key.
> Tests are also designed to be fully network-free — no key is needed to run `pytest`.

### Start the backend

```bash
uvicorn app.main:app --reload
```

Runs on **http://localhost:8000**.

The SQLite database (`backend/servora.db`) is created and seeded with demo data
automatically on first startup — you do not need to run any migration commands.

**If you pull changes that touch `app/db/models.py`** (a new column on an
existing table), delete `backend/servora.db` before restarting the
backend. `Base.metadata.create_all()` creates missing *tables* but does
not add columns to a table that already exists — an existing local
`servora.db` will throw `OperationalError: no such column` until the
file is deleted and reseeded from scratch. (This project has no
migration tool; see `CLAUDE.md`'s Open Questions for the same caveat
applied to the real deployed Postgres database, which needs an actual
`ALTER TABLE` instead of a delete-and-reseed.)

---

## 3. Frontend setup

Open a **separate terminal**. All commands below are run from the **`frontend/`** directory.

```bash
cd frontend
```

### Create the environment file

```bash
# Windows PowerShell / cmd
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

### Install dependencies

```bash
npm ci
```

### Start the frontend

```bash
npm run dev
```

Runs on **http://localhost:5173**.

---

## 4. Verify the setup

| Check | How |
|-------|-----|
| Backend health | `curl http://localhost:8000/health` → `{"status":"ok"}` |
| Frontend loads | Open http://localhost:5173 in a browser |
| Live AI chat | Requires a valid `ANTHROPIC_API_KEY` in `backend/.env` |

---

## 5. Run tests and checks locally

Run these before opening a PR (CI runs them automatically too):

**Backend tests**
```bash
# from backend/  (with the virtual environment activated)
pytest
```

**Frontend lint**
```bash
# from frontend/
npm run lint
```

**Frontend production build**
```bash
# from frontend/
npm run build
```

---

## 6. CI (GitHub Actions)

Every pull request into `main` and every push to `main` triggers two parallel jobs:

| Job | What it checks |
|-----|---------------|
| `backend` | `pytest` with Python 3.12 |
| `frontend` | `npm run lint` + `npm run build` with Node 22 |

CI does **not** use a real Anthropic API key. Tests must remain network-free.
See [`.github/workflows/ci.yml`](.github/workflows/ci.yml) for the full workflow.

---

## 7. Contribution workflow

1. Pick an open issue (they are prioritized — start at P0 if you are not sure
   what to take, since later issues depend on earlier ones).
2. Branch off `main`: `git checkout -b issue-<number>-short-name`.
3. Keep changes scoped to the issue. If you find yourself needing to change
   a shared contract (an agent return shape, an API route schema),
   flag it in the issue/PR description — several other issues depend on
   what is already there.
4. Run `pytest` from `backend/` and `npm run lint && npm run build` from
   `frontend/` before opening the PR.
5. Open a PR into `main` referencing the issue (`Closes #<number>`).
