"""Session-wide test setup.

Real bug found while writing issue #14's tests: a bare `TestClient(app)`
(used at module level in test_health.py and test_tickets_api.py) does
NOT reliably trigger FastAPI's ASGI lifespan (the `create_all()` +
`seed_if_empty()` in app/main.py) in this environment — only
`with TestClient(app) as client:` is guaranteed to. Every test written
before issue #14 happened to avoid this gap entirely: either every agent
touching the DB was mocked (test_health.py's existing tests), or the
test built its own isolated in-memory engine directly
(test_specialists.py, test_memory.py, test_orchestrator.py) rather than
going through the app's real file-based DB at all. Issue #14's tests are
the first to actually need real seeded data through a bare TestClient,
which is what surfaced this.

Fixing it here rather than converting every test file to a context
manager: guarantee the schema exists and is seeded once, before any test
runs, regardless of whether a given TestClient triggers lifespan.
"""
from app.db.database import Base, engine
from app.db.seed import seed_if_empty


def pytest_configure(config):
    Base.metadata.create_all(bind=engine)
    seed_if_empty()
