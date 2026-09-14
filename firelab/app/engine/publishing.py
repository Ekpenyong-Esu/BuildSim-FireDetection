"""Everything that writes the visual state out to BuildSim.

The publisher module turns state into payloads; this module decides what is
worth sending and when, which is a separate problem: BuildSim is slow enough
that sending everything on every tick would stall the simulation.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from ...adapters import publisher
from ...adapters.buildsim import BuildSimError
from . import actuation
from .constants import MAX_SENSOR_WRITES, PUBLISH_EVERY

if TYPE_CHECKING:
    from .state import EngineState


async def publish(engine: EngineState) -> None:
    """Send the whole visual state to BuildSim in one burst of parallel calls."""
    if not engine.connected:
        return
    states = {key: a.state for key, a in engine.agents.items() if a.state != "NORMAL"}
    burning = {
        s.space for s in engine.sources if s.kind in ("flaming", "smouldering", "cooking")
    } & set(engine.world.spaces)
    # Only draw flames once there is visible smoke, not the instant it lights.
    burning = {key for key in burning if engine.world.spaces[key].smoke > 0.05}

    tasks = [
        engine.client.put_room_layers(publisher.room_layers(engine.world, engine.probabilities)),
        engine.client.put_effects(publisher.effects(engine.world, burning)),
        engine.client.put_alerts(publisher.alerts(engine.world, states, engine.probabilities)),
        engine.client.put_entities(
            publisher.entities(
                engine.world, engine.occupants, int(PUBLISH_EVERY * 1000), engine.bounds
            )
        ),
        engine.client.put_occupancy(publisher.occupancy(engine.world, engine.occupants)),
        # Publishing danger here is what lets BuildSim route people around the
        # fire rather than merely refusing the path it would otherwise return.
        engine.client.put_doors(
            publisher.doors(engine.world, engine.doors, actuation.danger(engine))
        ),
    ]
    tasks.extend(await session_writes(engine, states))
    tasks.extend(sensor_writes(engine))

    # All at once, and the first failure marks us disconnected.
    for result in await asyncio.gather(*tasks, return_exceptions=True):
        if isinstance(result, BuildSimError):
            engine.connected = False
            engine.log("error", str(result))
            break


async def session_writes(engine: EngineState, states: dict[str, str]) -> list:
    """The viewer re-frames its camera on every route it is sent and
    repaints on every highlight, so only push these when they change."""
    viewer = engine.client.viewer
    session_id = await viewer.session_id(time.monotonic())
    if not session_id:
        return []
    writes = []
    highlights = publisher.highlights(engine.world, states)
    if highlights != engine.last_highlights:
        engine.last_highlights = highlights
        writes.append(viewer.put_highlights(session_id, highlights))
    route = engine.evacuation.display_route
    level = engine.evacuation.display_level
    # Keyed by tab as well: a reloaded or newly opened viewer has never been
    # sent the route, however unchanged it is. An empty route is sent too,
    # once, because that is how the viewer is told to erase the old line.
    drawn = (session_id, route, level)
    if drawn != engine.last_route and (route or engine.last_route is not None):
        writes.append(_put_route(engine, drawn))
    return writes


async def _put_route(engine: EngineState, drawn: tuple[str, list[dict], str]) -> None:
    """Draw a route, and only then remember it as drawn, so a failure is retried."""
    session_id, route, level = drawn
    await engine.client.viewer.put_route(session_id, publisher.route(route, level))
    engine.last_route = drawn


def sensor_writes(engine: EngineState) -> list:
    """Push a few pending readings into BuildSim's sensor labels.

    Only a handful per publish: with 2868 devices, sending them all would
    bury BuildSim.
    """
    writes = []
    for device_id, value in list(engine.pending_writes.items())[:MAX_SENSOR_WRITES]:
        del engine.pending_writes[device_id]
        writes.append(engine.client.set_sensor_value(f"{device_id}-val", f"{value:.3f}"))
    return writes
