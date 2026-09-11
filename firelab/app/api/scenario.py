"""Setting up what happens: fires, nuisances and the one-click presets."""

from fastapi import APIRouter, HTTPException

from .. import presets as presets_mod
from ..engine import devices, scenario
from ..runtime import engine
from .models import IgniteBody, PresetBody

router = APIRouter()


@router.post("/api/scenario/ignite")
async def ignite(body: IgniteBody) -> dict:
    """Start a fire or a nuisance in one room."""
    try:
        return scenario.ignite(
            engine, body.space, body.kind, body.growth, body.delay, body.peak_kw
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/scenario/preset")
async def apply_preset(body: PresetBody) -> dict:
    """Run a preset in a room: ignite it, and inject its fault if it has one."""
    try:
        result = scenario.apply_preset(engine, body.preset, body.space)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await devices.register(engine)
    return result


@router.delete("/api/scenario/{source_id}")
async def extinguish(source_id: str) -> dict:
    """Put a source out. The heat and smoke it made still have to disperse."""
    scenario.remove_source(engine, source_id)
    return {"ok": True}


@router.get("/api/presets")
async def list_presets() -> list[dict]:
    """The six one-click scenarios."""
    return presets_mod.catalogue()
