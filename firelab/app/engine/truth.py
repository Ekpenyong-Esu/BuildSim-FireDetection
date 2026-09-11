"""The zones that are allowed to read the ground truth.

WORLD advances the physics, SENSING turns the truth into readings, and exposure
charges each person for the CO they breathe. Everything downstream of this file
works from readings alone — see `intelligence.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domain import physics, sensing, sources, tenability
from ...domain.features import Window

if TYPE_CHECKING:
    from .state import EngineState


def advance(engine: EngineState, dt: float) -> None:
    """WORLD: work out what every source is emitting, then advance the world."""
    emissions: dict[str, tuple[float, float, float]] = {}
    for source in engine.sources:
        heat, smoke, co = sources.emission(source, engine.now)
        if heat == 0.0 and smoke == 0.0 and co == 0.0:
            continue  # not lit yet, or burnt out
        # Two sources in one room simply add up.
        prev = emissions.get(source.space, (0.0, 0.0, 0.0))
        emissions[source.space] = (prev[0] + heat, prev[1] + smoke, prev[2] + co)
    physics.step(engine.world, emissions, dt)


def sense(engine: EngineState, dt: float) -> None:
    """SENSING: let each device look at the truth and report what it thinks."""
    for device in engine.devices.values():
        space = engine.world.spaces.get(device.space)
        if space is None:
            continue
        truth = getattr(space, device.modality)  # the real temperature/smoke/CO
        value = sensing.sample(device, truth, engine.now, dt, engine.rng)
        if value is None:
            continue  # not due yet, or the device is dead
        engine.windows.setdefault(device.space, Window(space=device.space)).add(
            device.modality, engine.now, value
        )
        engine.pending_writes[device.id] = value


def expose(engine: EngineState, dt: float) -> None:
    """Add this step's CO dose to everyone still inside.

    Dose is carried by the person, not the room: walking out through a smoke
    logged corridor costs you, and it keeps costing you afterwards.
    """
    for occupant in engine.occupants:
        if occupant.safe:
            continue
        space = engine.world.spaces.get(occupant.space)
        if space is not None:
            occupant.fed += tenability.fed_increment(space.co, dt)
