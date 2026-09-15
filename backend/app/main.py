import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import analytics, booking, bookings, chat, explanations, integrations, investigations, kb, notifications, records, stream, tickets
from app.config import settings
from app.db.database import Base, engine
from app.db.seed import seed_if_empty

_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_if_empty()
    yield


app = FastAPI(title="Servora API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """General safety net for the CORS/opaque-error class of bug this
    project has hit repeatedly (issue #17 fixed it for ONE specific
    exception type in llm.py; app/api/booking.py's/chat.py's LLMError
    catches fixed it for ONE specific call site each — see their own
    comments). Any OTHER unhandled exception, anywhere in a route, still
    reached Starlette's default handling, which returns a bare response
    with no CORS headers at all — the browser's fetch() can't even read
    it, so it only ever shows as an opaque "Failed to fetch", not the
    real reason, and the actual error was only visible in server logs
    someone had to go looking at.

    This does NOT change the existing, more specific handlers:
    FastAPI/Starlette always prefers the most specific handler found by
    walking the exception's MRO, so a raised `HTTPException` (this
    project's existing, deliberate way of returning a 4xx/5xx with a real
    `detail` message) and `RequestValidationError` (422s) are matched by
    their own built-in handlers first and never reach this one — this
    only ever fires for a truly unexpected error.

    The client gets a generic, safe message — never the exception's own
    text, a stack trace, or anything else that might leak internals
    (a DB connection string in a SQLAlchemy error, a file path, etc.).
    The real exception (with its full traceback) is logged server-side
    via `_log.exception(...)` for whoever needs to actually debug it.

    A Starlette mechanic worth being explicit about, since it's the
    actual reason this handler needs to do more than just return a
    JSONResponse: a handler registered for the base `Exception` type (or
    status code 500) is invoked by the OUTERMOST middleware
    (ServerErrorMiddleware — see Starlette's own
    `Starlette.build_middleware_stack()`), which sits OUTSIDE
    CORSMiddleware and sends its response via the raw ASGI `send` it was
    originally given, never passing through CORSMiddleware at all
    (confirmed directly against Starlette's source, and empirically in
    tests/test_error_handling.py). So CORSMiddleware's own header
    injection never happens for this path — the CORS header has to be
    added by hand here, replicating exactly what CORSMiddleware would
    have done for the SAME configured origin (see the `add_middleware`
    call above): only the ONE configured `frontend_origin`, mirrored back
    verbatim with a `Vary: Origin`, never a wildcard `*` — this must stay
    in sync with that CORSMiddleware call if it's ever reconfigured.
    """
    _log.exception("Unhandled exception on %s %s", request.method, request.url.path)
    response = JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )
    origin = request.headers.get("origin")
    if origin == settings.frontend_origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    return response

app.include_router(chat.router)
app.include_router(tickets.router)
app.include_router(analytics.router)
app.include_router(kb.router)
app.include_router(booking.router)
app.include_router(bookings.router)
app.include_router(notifications.router)
app.include_router(stream.router)
app.include_router(investigations.router)
app.include_router(explanations.router)
app.include_router(records.router)
app.include_router(integrations.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
