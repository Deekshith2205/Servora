"""Session-wide test setup.

Three real bugs found by writing tests carefully, all fixed here:

1. (Issue #14) A bare `TestClient(app)` (used at module level in several
   test files) does NOT reliably trigger FastAPI's ASGI lifespan (the
   `create_all()` + `seed_if_empty()` in app/main.py) in this
   environment — only `with TestClient(app) as client:` is guaranteed
   to. Fixed by guaranteeing the schema exists and is seeded once here,
   regardless of whether a given TestClient triggers lifespan.

2. (Issue #17) Several test files call `SessionLocal()` directly and
   mutate the DB (e.g. `db.query(Ticket).delete()`) — before this fix,
   that pointed at the SAME file-based `servora.db` the local dev server
   uses, so running `pytest` wiped real seeded/demo data out from under
   a running `uvicorn --reload`. This surfaced as a genuine, unrelated
   test *failure* once enough test files did this (test_tickets_api.py's
   seeded-ticket test started failing because an earlier test file had
   already deleted all tickets) — not just a dev-workflow annoyance.

   Fixed by pointing DATABASE_URL at an isolated, throwaway SQLite file
   before app.config (and therefore app.db.database's module-level
   engine) is ever imported — this MUST happen at the top of this file,
   before the imports below, since Settings() and the engine are both
   read/created once at first import.

3. (Found adding the Gemini provider) The exact same class of bug as #2,
   for a different setting: `LLM_PROVIDER` was a config field for a long
   time before it was ever actually branched on, so its value in a
   developer's local .env never mattered to test behavior. The moment
   `call_llm()` started dispatching on it for real, every existing test
   that mocks the Anthropic client (and never touches
   `settings.llm_provider` itself) started silently exercising whichever
   provider the machine's own `backend/.env` happened to have configured
   — passing or failing depending on a file that isn't even part of the
   repo. Fixed the same way as #2: force it to "anthropic" before
   app.config is ever imported, so the whole suite's default is
   deterministic regardless of local `.env` content. The Gemini-specific
   tests (test_llm_gemini.py) still work fine — they explicitly
   `@patch("app.config.settings.llm_provider", "gemini")` per test, which
   overrides this default for the duration of that test only.
"""
import os
import shutil
import tempfile

_TEST_DB_PATH = os.path.join(tempfile.gettempdir(), "servora_test.db")
if os.path.exists(_TEST_DB_PATH):
    os.remove(_TEST_DB_PATH)  # fresh schema/seed every pytest invocation
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ["LLM_PROVIDER"] = "anthropic"

# [RAG] same class of test-pollution bug as the SQLite DB above (see #2
# in this file's own docstring): without this, `pytest` would read/write
# the real dev server's on-disk `backend/chroma_data/` vector index.
# See `app/services/vector_store.py::_persist_dir()` for the read side.
_TEST_CHROMA_DIR = os.path.join(tempfile.gettempdir(), "servora_test_chroma")
if os.path.exists(_TEST_CHROMA_DIR):
    shutil.rmtree(_TEST_CHROMA_DIR, ignore_errors=True)
os.environ["CHROMA_PERSIST_DIR"] = _TEST_CHROMA_DIR

# Same reasoning, for uploaded document bytes — see
# app/services/knowledge_retrieval.py::_upload_dir().
_TEST_UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "servora_test_uploads")
if os.path.exists(_TEST_UPLOAD_DIR):
    shutil.rmtree(_TEST_UPLOAD_DIR, ignore_errors=True)
os.environ["UPLOAD_DIR"] = _TEST_UPLOAD_DIR
# /api/chat and /api/booking are rate-limited in real use (see
# app/rate_limit.py) — every test here mocks the LLM client, so a single
# test file can legitimately send far more requests in a few seconds
# than any real caller would; without this override, that would trip a
# limit meant for real abuse, not a fast local test run.
os.environ["RATE_LIMIT_ENABLED"] = "false"
# [RAG] see app/db/seed.py::seed_knowledge_documents_if_missing()'s own
# docstring — without this, every test that reaches seed_if_empty()
# would make 3 real Gemini embedding API calls against whatever
# GOOGLE_API_KEY happens to be in a developer's local .env.
os.environ["SEED_KNOWLEDGE_DOCUMENTS"] = "false"

from app.db.database import Base, engine  # noqa: E402 (must come after the overrides above)
from app.db.seed import seed_if_empty  # noqa: E402


def pytest_configure(config):
    Base.metadata.create_all(bind=engine)
    seed_if_empty()
