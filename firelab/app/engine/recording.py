"""The flight recorder: one row of truth beside reading, now and then.

It is the one place that deliberately sees both sides at once, which is exactly
why it cannot live in `intelligence.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .state import EngineState


def record(engine: EngineState) -> None:
    """Save a row of truth-and-reading for every monitored room, now and then."""
    if not engine.history.due(engine.now):
        return
    rows = {}
    for key in engine.windows:
        space = engine.world.spaces.get(key)
        if space is None:
            continue
        reading = engine.features.get(key)
        rows[key] = [
            round(space.temperature, 2),
            round(space.smoke, 4),
            round(space.co, 1),
            round(reading.temperature, 2) if reading else None,
            round(reading.smoke, 4) if reading else None,
            round(reading.co, 1) if reading else None,
            round(engine.probabilities.get(key, 0.0), 3),
        ]
    engine.history.record(engine.now, rows)
