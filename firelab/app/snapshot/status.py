"""Header numbers: the clock, the BuildSim connection and the tallies."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..engine.state import EngineState


def clock(engine: EngineState) -> dict:
    """Simulated time, both as a number and as a readable hh:mm:ss."""
    hours, remainder = divmod(int(engine.now) % 86400, 3600)  # wrap at midnight
    minutes, seconds = divmod(remainder, 60)
    return {
        "seconds": round(engine.now, 1),
        "text": f"{hours:02d}:{minutes:02d}:{seconds:02d}",
        "running": engine.running,
        "factor": engine.config.factor,
    }


def buildsim(engine: EngineState) -> dict:
    """Whether the 3D viewer is reachable and how much of it has been loaded."""
    return {
        "url": engine.config.buildsim_url,
        "connected": engine.connected,
        "loaded": engine.loaded,
        "levels": list(engine.floors),
        "spaces": len(engine.world.spaces),
    }


def counts(engine: EngineState) -> dict:
    """The headline numbers along the top of the UI."""
    return {
        "devices": len(engine.devices),
        "faulty": sum(1 for d in engine.devices.values() if d.fault != "none"),
        "alarms": sum(
            1 for a in engine.agents.values() if a.state in ("CONFIRMED", "SUPPRESSED")
        ),
        "evacuating": sum(1 for o in engine.occupants if o.status == "evacuating"),
        "safe": sum(1 for o in engine.occupants if o.safe),
        "occupants": len(engine.occupants),
    }
