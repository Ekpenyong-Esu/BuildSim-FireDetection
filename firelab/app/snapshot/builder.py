"""Assemble the one dictionary that is the entire contract with the UI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import population as population_mod
from . import safety, spaces, status

if TYPE_CHECKING:
    from ..engine.state import EngineState


def build(engine: EngineState) -> dict:
    """A full picture of the simulation, small enough to push every tick.

    This one dictionary is the entire contract with the UI. Nothing in the
    browser reaches past it into the engine.
    """
    return {
        "clock": status.clock(engine),
        "buildsim": status.buildsim(engine),
        "detector": engine.detector.name,
        "auto": engine.config.response.auto,
        "spaces": spaces.spaces(engine),
        "sources": [dict(s.__dict__) for s in engine.sources],
        "counts": status.counts(engine),
        "population": population_mod.population(engine),
        "tenability": safety.tenability_report(engine),
        "score": engine.score.summary(),
        "evacuation": safety.evacuation(engine),
        "journal": engine.journal[-40:],  # the newest entries only
    }
