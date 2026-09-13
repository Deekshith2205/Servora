"""[SWARM] issue #79: GET /api/investigations/stream/{stream_key} — the
SSE endpoint a live-mode frontend opens BEFORE calling POST /api/chat
(with the same stream_key in its body). See app/services/stream_bus.py
for the pub/sub this reads from and why it's a plain thread-safe
`queue.Queue`, not `asyncio.Queue`.

Plain `StreamingResponse` with hand-formatted `text/event-stream` lines
rather than adding a third-party SSE library — the format itself is
trivial (`event: <name>\ndata: <json>\n\n`) and this project otherwise
keeps its dependency footprint minimal (see requirements.txt).
"""
import asyncio
import json
import queue

from fastapi import APIRouter
from starlette.responses import StreamingResponse

from app.services import stream_bus

router = APIRouter(prefix="/api/investigations", tags=["stream"])

# How long to wait on one queue.get() before yielding a keepalive comment.
# Keeps the underlying HTTP connection from looking idle/dead to proxies
# and gives the generator a chance to notice a client disconnect.
_POLL_TIMEOUT_S = 15
# Total time to wait with NO real event at all before giving up entirely —
# guards against a stream_key that's opened but whose /api/chat call never
# actually starts (e.g. the request never arrives), which would otherwise
# leak a queue + this connection forever.
_MAX_IDLE_S = 120


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _event_generator(stream_key: str):
    q = stream_bus.subscribe(stream_key)
    loop = asyncio.get_event_loop()
    idle_s = 0.0
    try:
        while True:
            try:
                item = await loop.run_in_executor(None, q.get, True, _POLL_TIMEOUT_S)
            except queue.Empty:
                idle_s += _POLL_TIMEOUT_S
                if idle_s >= _MAX_IDLE_S:
                    yield _sse("timeout", {})
                    return
                yield _sse("keepalive", {})
                continue

            idle_s = 0.0
            if item is None:  # the sentinel stream_bus.close() sends
                yield _sse("end", {})
                return
            yield _sse("message", item)
    finally:
        stream_bus.cleanup(stream_key)


@router.get("/stream/{stream_key}")
async def stream_investigation(stream_key: str) -> StreamingResponse:
    return StreamingResponse(_event_generator(stream_key), media_type="text/event-stream")
