"""Starting a fresh run: the seed, the people, and clearing the board.

Resetting is not the same as reloading. This keeps the floor plans and the
sensors you installed; only what happened during the run is thrown away.
"""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING

from ...domain import occupants as occupants_mod

if TYPE_CHECKING:
    from .state import EngineState


def place_occupants(engine: EngineState, population: dict[str, int]) -> None:
    """Scatter people through the building again."""
    engine.occupants = occupants_mod.place(engine.world.spaces.values(), population, engine.rng)
    engine.mark_dirty()


def reseed(engine: EngineState) -> None:
    """Restart the randomness, so the next run repeats exactly."""
    engine.rng = Random(engine.config.seed)


def reset(engine: EngineState) -> None:
    """Back to a quiet building. Keeps the floor plans and the sensors."""
    engine.world.reset()
    engine.sources.clear()
    engine.probabilities.clear()
    engine.features.clear()
    for window in engine.windows.values():
        window.series.clear()
    for device in engine.devices.values():
        device.internal = 20.0 if device.modality == "temperature" else 0.0
        device.reading = None
        device.drift = 0.0
        device.history.clear()
    for room_agent in engine.agents.values():
        room_agent.state = "NORMAL"
        room_agent.probability = 0.0
        room_agent.above_since = None
        room_agent.below_since = None
    engine.doors.clear()
    engine.evacuation.reset()
    engine.score.clear()
    engine.history.clear()
    engine.last_route = None
    engine.last_highlights = None
    place_occupants(engine, engine.config.population)
    engine.log("info", "simulation reset")
