"""Health, the current snapshot, the room list and the settings."""

from fastapi import APIRouter

from ..engine import building, session
from ..runtime import engine

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict:
    """Are we up, and can we still see BuildSim?"""
    return {"ok": True, "buildsim": engine.connected}


@router.get("/api/state")
async def state() -> dict:
    """The current snapshot, for anything that cannot use the event stream."""
    return engine.snapshot()


@router.get("/api/rooms")
async def rooms() -> list[dict]:
    """All 956 rooms, for the room picker."""
    return engine.rooms()


@router.get("/api/config")
async def get_config() -> dict:
    """Read the current settings."""
    return engine.config.to_dict()


@router.put("/api/config")
async def put_config(patch: dict) -> dict:
    """Change some settings. Send only the fields you want to change."""
    engine.config.apply(patch)
    if "seed" in patch:
        session.reseed(engine)  # a run is only repeatable if the randomness restarts too
    return engine.config.to_dict()


@router.post("/api/reload")
async def reload() -> dict:
    """Re-read the floor plans from BuildSim."""
    await building.load(engine)
    return engine.snapshot()["buildsim"]
