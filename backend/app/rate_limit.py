"""A minimal per-IP rate limiter for the endpoints that trigger a real
LLM call chain (`/api/chat`, `/api/booking`) — each one can fan out into
several real model calls (classifier + planner + specialist(s) + critic,
sometimes multiple specialists in parallel, see [SWARM] #88), so an
unthrottled endpoint is a real cost and abuse risk once this app is
reachable by anyone other than its own developers, not just a
theoretical one — confirmed live while testing this: a burst of manual
requests during development alone was enough to hit a free-tier
provider key's own rate limit.

Deliberately NOT a third-party dependency (slowapi, etc.) — a plain
in-memory sliding window is the whole mechanism this needs, matches this
codebase's own "reuse what exists, keep dependencies minimal"
convention, and needs zero extra infrastructure (no Redis) for a
single-process demo deployment. The one real limitation that comes with
that — the window resets if the process restarts, and doesn't share
state across multiple worker processes — is an explicit, acceptable
tradeoff for this app's actual deployment shape (one `uvicorn` process),
not an oversight.
"""
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request

from app.config import settings

# {client_key: deque[timestamp, ...]} — each deque holds only the
# timestamps still inside the current window; older ones are dropped on
# every check, so this never grows unbounded for a single active client.
_hits: dict[str, deque] = defaultdict(deque)
_lock = Lock()


def _client_key(request: Request) -> str:
    """The real client IP when available (a request that reached this
    process through nothing but FastAPI's own dev server has no proxy
    stripping X-Forwarded-For to worry about) — falls back to a shared
    bucket only if the ASGI server genuinely reports no client at all,
    which real HTTP requests never do."""
    if request.client:
        return request.client.host
    return "unknown"


def rate_limit(request: Request) -> None:
    """FastAPI dependency: `Depends(rate_limit)`. Raises a real 429 with
    a readable detail (matching this codebase's established convention —
    see api/client.js's own comment on why a bare status code isn't
    enough) once a client exceeds `settings.rate_limit_requests` calls
    within `settings.rate_limit_window_seconds`."""
    if not settings.rate_limit_enabled:
        return

    key = _client_key(request)
    now = time.monotonic()
    window_start = now - settings.rate_limit_window_seconds

    with _lock:
        hits = _hits[key]
        while hits and hits[0] < window_start:
            hits.popleft()

        if len(hits) >= settings.rate_limit_requests:
            retry_after = max(1, round(settings.rate_limit_window_seconds - (now - hits[0])))
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Too many requests — please wait {retry_after}s before trying again. "
                    "Each message here triggers a real AI investigation, so this limit protects "
                    "the demo from being rate-limited or running up cost for everyone."
                ),
                headers={"Retry-After": str(retry_after)},
            )

        hits.append(now)
