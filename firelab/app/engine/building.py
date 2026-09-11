"""Turning BuildSim's floor plans into the world the physics runs on."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...adapters.buildsim import BuildSimError
from ...adapters.exits import derive_exits
from ...adapters.world_builder import build_world, page_bounds
from . import session

if TYPE_CHECKING:
    from .state import EngineState


async def load(engine: EngineState) -> None:
    """Fetch floors from BuildSim and rebuild the world."""
    engine.connected = await engine.client.health()
    if not engine.connected:
        engine.log("error", "BuildSim is not reachable at " + engine.config.buildsim_url)
        return
    floors = {}
    for level in engine.config.levels:
        try:
            floors[level] = await engine.client.floor(level)
        except BuildSimError as exc:
            engine.log("error", f"could not load {level}: {exc}")
    if not floors:
        return  # nothing loaded, so keep whatever world we already had
    engine.floors = floors
    engine.bounds = page_bounds(floors)
    engine.world, engine.entries = build_world(floors)
    engine.config.exits = derive_exits(floors, engine.config.exits)
    engine.loaded = True
    engine.log(
        "info",
        f"loaded {len(engine.world.spaces)} spaces and "
        f"{len(engine.world.couplings)} couplings from {', '.join(floors)}",
    )
    session.place_occupants(engine, engine.config.population)
