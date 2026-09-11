"""The live state stream the browser holds open."""

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..runtime import engine

router = APIRouter()


@router.get("/api/events")
async def events() -> StreamingResponse:
    """Server-sent events: the browser holds this open and receives every tick.

    Push beats polling here because the snapshot changes on the engine's clock,
    not the browser's.
    """
    queue = engine.subscribe()

    async def stream():
        try:
            yield f"data: {json.dumps(engine.snapshot())}\n\n"  # current state first
            while True:
                try:
                    snapshot = await asyncio.wait_for(queue.get(), timeout=5.0)
                    yield f"data: {json.dumps(snapshot)}\n\n"
                except asyncio.TimeoutError:
                    # Nothing happened for 5 s. Send anyway, to keep the
                    # connection from being closed by a proxy.
                    yield f"data: {json.dumps(engine.snapshot())}\n\n"
        finally:
            engine.unsubscribe(queue)  # always tidy up, even on disconnect

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
