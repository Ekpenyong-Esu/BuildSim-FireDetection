"""The engine.

`core` holds the state and the tick loop; every other module is one thing the
engine can be asked to do, and takes the engine as its first argument.

    building      floor plans -> the world the physics runs on
    session       reseed, re-scatter people, clear the board
    scenario      light fires and nuisances, apply presets
    devices       install, remove and break sensors
    truth         WORLD and SENSING: the only readers of the ground truth
    intelligence  readings -> features -> P(fire) -> the room state machine
    actuation     interlocks, then act
    recording     the flight recorder: truth beside reading
    publishing    what to write to BuildSim, and when
    streaming     snapshot fan-out to the open browsers
"""

from .constants import MAX_SENSOR_WRITES, PUBLISH_EVERY, REAL_TICK
from .core import Engine

__all__ = ["Engine", "MAX_SENSOR_WRITES", "PUBLISH_EVERY", "REAL_TICK"]
