"""Running the clock: play, pause, fast-forward, start again."""

from fastapi import APIRouter

from ..engine import session
from ..runtime import engine
from .models import ClockBody

router = APIRouter()


@router.post("/api/clock")
async def clock(body: ClockBody) -> dict:
    """Play, pause, jump in time, or change how fast time runs."""
    engine.set_clock(body.seconds, body.factor)
    if body.running is not None:
        engine.set_running(body.running)
    return engine.snapshot()["clock"]


@router.post("/api/reset")
async def reset() -> dict:
    """Clear the fires, the alarms and the scorecard; keep the building."""
    session.reset(engine)
    return {"ok": True}
