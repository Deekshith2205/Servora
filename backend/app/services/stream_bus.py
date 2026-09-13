"""[SWARM] issue #79: minimal in-process pub/sub backing true live
streaming of investigation progress.

Design choice (see the issue's own "Option A vs B" discussion): `/api/chat`
stays fully synchronous — the source of truth is unchanged. The frontend
generates a `stream_key` (a UUID) BEFORE calling `/api/chat`, opens
`GET /api/investigations/stream/{stream_key}` (SSE) concurrently, and
`orchestrator.py::handle_message()` publishes one event here per pipeline
stage as it completes, keyed by that same string. Both requests are in
flight on the same browser tab at once.

Plain `queue.Queue` (thread-safe stdlib), not `asyncio.Queue`: FastAPI runs
a synchronous `def` path operation (like `POST /api/chat`, and therefore
`handle_message()`) in a worker thread, not on the event loop — an
`asyncio.Queue` isn't safely writable from there without extra
coordination. The async SSE endpoint reads this queue via
`run_in_executor`, which is the correct way to block a worker thread from
async code without blocking the event loop.

No persistence, no cross-process concern: this is a single-process
hackathon deployment (see docs/ARCHITECTURE.md), so an in-memory dict is
the right amount of infrastructure — not a message broker.
"""
import queue
import threading

# Each stream_key gets exactly one queue, created on first use by whichever
# side (publisher or subscriber) gets there first — order between
# "frontend opens the SSE connection" and "the orchestrator's first
# _record() call" is not guaranteed, so both sides must be able to create
# it.
_lock = threading.Lock()
_queues: dict[str, "queue.Queue"] = {}


def _get_queue(stream_key: str) -> "queue.Queue":
    with _lock:
        if stream_key not in _queues:
            _queues[stream_key] = queue.Queue()
        return _queues[stream_key]


def publish(stream_key: str, event: dict) -> None:
    """Called from orchestrator.py's _record() — one event per pipeline
    stage, in real time, as that stage actually completes."""
    _get_queue(stream_key).put(event)


def close(stream_key: str) -> None:
    """Signals "no more events" — a `None` sentinel, since a plain
    `queue.Queue` has no built-in close/end-of-stream concept."""
    _get_queue(stream_key).put(None)


def subscribe(stream_key: str) -> "queue.Queue":
    """Called from the SSE endpoint — returns the same queue `publish()`
    writes to, creating it if the SSE connection opens first."""
    return _get_queue(stream_key)


def cleanup(stream_key: str) -> None:
    """Called once the SSE endpoint's generator finishes (client
    disconnected, or the sentinel was seen) — without this, a stream_key
    that's opened once and never reused would leak its queue for the
    life of the process."""
    with _lock:
        _queues.pop(stream_key, None)
