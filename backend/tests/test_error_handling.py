"""Tests for the general unhandled-exception handler (app/main.py).

Closes the general CORS/opaque-error gap issue #17 only fixed for ONE
specific exception type (a bare TypeError in llm.py), and
app/api/chat.py's / app/api/booking.py's own LLMError catches only fixed
for ONE call site each — see each of those comments, and CLAUDE.md's
"Open questions" section, for the full history.

Two things a truly unhandled exception must do that neither an
HTTPException nor a mocked LLMError already prove: (1) still carry real
CORS headers back to the browser, and (2) never leak the exception's own
message/type/traceback to the client, only a generic safe string — while
the actual exception is still logged server-side for debugging. Reuses a
real, already-mocked route (`POST /api/chat`) rather than adding a
test-only endpoint, by making a mocked-out internal call raise a plain
exception `/api/chat`'s own `except LLMError:` does NOT catch — the
closest thing to "some unrelated bug somewhere in the pipeline", which is
exactly the class of error this handler exists for.

A real Starlette mechanic worth being explicit about, found writing
these tests: a handler registered for the base `Exception` type (or
status code 500) is pulled out of ExceptionMiddleware and passed to the
OUTER ServerErrorMiddleware instead (see Starlette's
`Starlette.build_middleware_stack()`), which sits OUTSIDE CORSMiddleware
— and, per its own source, sends our handler's response using the RAW
ASGI `send` it was originally given, not the CORS-wrapped one it passed
further down to CORSMiddleware/the router. It then deliberately
re-raises the original exception afterward (so a real server still logs
it, and so `TestClient`'s default `raise_server_exceptions=True` can
propagate it into a test — which is why the tests that intentionally
trigger this path below use `raise_server_exceptions=False` to inspect
the response instead). Whether CORS headers actually survive this path
is exactly what the test below empirically settles, rather than assumed
from the implementation.
"""
import logging

from fastapi.testclient import TestClient

from app.db.database import SessionLocal
from app.db.models import Customer
from app.main import app

_email_counter = 0


def _seed_customer(db):
    global _email_counter
    _email_counter += 1
    customer = Customer(name="Error Handling Test Customer", email=f"error-handling-{_email_counter}@example.com")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def test_unexpected_exception_becomes_a_consistent_500_json_body(monkeypatch):
    """Not a 502/LLMError shape (that's a different, already-handled
    case) — a genuinely unexpected error, e.g. a bug somewhere in the
    pipeline that isn't LLMError at all."""
    db = SessionLocal()
    customer = _seed_customer(db)

    def _boom(message):
        raise RuntimeError("a secret internal detail that must never reach the client")

    monkeypatch.setattr("app.orchestrator.classify", _boom)

    # See this module's docstring: ServerErrorMiddleware re-raises after
    # sending the response, by design — opt out of TestClient's default
    # re-raise so we can inspect the response it already sent.
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/api/chat",
            json={"customer_id": customer.id, "message": "hello"},
            headers={"origin": "http://localhost:5173"},
        )

    assert resp.status_code == 500
    body = resp.json()
    # Consistent shape: the same "detail" key every HTTPException-based
    # error response in this codebase already uses.
    assert set(body.keys()) == {"detail"}
    assert body["detail"] == "An unexpected error occurred. Please try again."

    # The actual exception text/type must never reach the client.
    raw_text = resp.text
    assert "RuntimeError" not in raw_text
    assert "a secret internal detail" not in raw_text
    assert "Traceback" not in raw_text


def test_unexpected_exception_response_still_carries_cors_headers(monkeypatch):
    """The specific bug this handler exists to close: an unhandled
    exception that bypasses CORSMiddleware produces a response the
    browser's fetch() can't even read (no Access-Control-Allow-Origin
    header) — it shows up as a bare "Failed to fetch", not a readable
    error. This must not happen anymore."""
    db = SessionLocal()
    customer = _seed_customer(db)

    monkeypatch.setattr("app.orchestrator.classify", lambda message: (_ for _ in ()).throw(RuntimeError("boom")))

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/api/chat",
            json={"customer_id": customer.id, "message": "hello"},
            headers={"origin": "http://localhost:5173"},
        )

    assert resp.status_code == 500
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_unexpected_exception_is_logged_server_side(monkeypatch, caplog):
    db = SessionLocal()
    customer = _seed_customer(db)

    monkeypatch.setattr(
        "app.orchestrator.classify",
        lambda message: (_ for _ in ()).throw(RuntimeError("only visible in the server log, never in the response")),
    )

    with caplog.at_level(logging.ERROR, logger="app.main"):
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post(
                "/api/chat",
                json={"customer_id": customer.id, "message": "hello"},
                headers={"origin": "http://localhost:5173"},
            )

    assert resp.status_code == 500
    assert any("Unhandled exception" in record.message for record in caplog.records)
    assert any("only visible in the server log" in record.exc_text for record in caplog.records if record.exc_text)


def test_http_exception_behavior_is_unchanged_by_the_new_handler():
    """A real, already-existing HTTPException path (an unknown ticket id)
    must still return its own specific status code and detail message —
    the new generic handler must never shadow it."""
    with TestClient(app) as client:
        resp = client.post("/api/booking", json={"customer_id": 999999, "messages": []})

    assert resp.status_code == 404
    assert resp.json() == {"detail": "Customer 999999 not found"}


def test_http_exception_response_still_carries_cors_headers():
    """Regression guard: confirms the pre-existing (correct) behavior
    this task must NOT change — HTTPException responses always went
    through CORSMiddleware already."""
    with TestClient(app) as client:
        resp = client.post(
            "/api/booking",
            json={"customer_id": 999999, "messages": []},
            headers={"origin": "http://localhost:5173"},
        )

    assert resp.status_code == 404
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_successful_response_is_unaffected():
    """The new handler must never fire, and must add nothing, on the
    normal success path."""
    with TestClient(app) as client:
        resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
