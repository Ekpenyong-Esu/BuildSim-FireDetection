"""Map simulation state onto BuildSim's visual and device APIs.

One module per writer, deliberately kept apart:

    layers    physics -> room-layers       what is physically true
    effects   physics -> particle effects  what is physically true
    beliefs   agent   -> highlights, alerts what the system believes
    people    people  -> entities, occupancy where the occupants are
    hardware  devices -> doors, equipment  what is installed in the building
    routes    a path  -> session route      the way out, drawn in the viewer
"""

from .beliefs import SEVERITY, STATE_COLOURS, alerts, highlights
from .effects import MAX_SMOKE_EFFECTS, SMOKE_THRESHOLD, effects
from .hardware import EQUIPMENT_TYPES, doors, equipment
from .layers import BELIEF, TRUTH, room_layers
from .people import EDGE_MARGIN, MAX_ENTITIES, entities, occupancy
from .routes import path_length, route

__all__ = [
    "BELIEF",
    "EDGE_MARGIN",
    "EQUIPMENT_TYPES",
    "MAX_ENTITIES",
    "MAX_SMOKE_EFFECTS",
    "SEVERITY",
    "SMOKE_THRESHOLD",
    "STATE_COLOURS",
    "TRUTH",
    "alerts",
    "doors",
    "effects",
    "entities",
    "equipment",
    "highlights",
    "occupancy",
    "path_length",
    "room_layers",
    "route",
]
