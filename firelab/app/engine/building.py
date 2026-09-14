"""Turning BuildSim's floor plans into the world the physics runs on."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...adapters.buildsim import BuildSimError
from ...adapters.world_builder import build_world, page_bounds, stair_couplings
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
    engine.world = build_world(floors)
    # The stairs are not in any one floor's graph, so they are asked for
    # separately. They serve twice over: people walk down them to a real exit,
    # and smoke climbs them. Without this the storeys are sealed from each other.
    stairs = []
    try:
        stairs = stair_couplings(await engine.client.cross_floor_edges(), engine.world.spaces)
        engine.world.couplings.extend(stairs)
    except BuildSimError as exc:
        # Not fatal: each floor still works on its own, but nothing joins them.
        engine.log("error", f"no cross-floor edges, storeys will be sealed: {exc}")
    engine.loaded = True
    engine.log(
        "info",
        f"loaded {len(engine.world.spaces)} spaces and "
        f"{len(engine.world.couplings)} couplings ({len(stairs)} stairwells) "
        f"from {', '.join(floors)}",
    )
    session.place_occupants(engine, engine.config.population)
