"""Map simulation state onto BuildSim's visual and device APIs.

Three writers, deliberately kept apart:

    physics -> room-layers + effects   what is physically true
    agent   -> highlights + alerts     what the system believes
    people  -> entities + occupancy    where the occupants are
"""

from typing import Iterable

from ..domain.occupants import Occupant
from ..domain.physics import World
from ..domain.sensing import Device

# Labels shown in the viewer's legend, so nobody confuses what is real with
# what the system merely thinks.
TRUTH = "simulation truth"
BELIEF = "decision-service estimate"


def room_layers(world: World, probabilities: dict[str, float]) -> list[dict]:
    """Four heat maps painted on the floors: three truths and one belief.

    Putting them side by side is the point of the whole project: you can see
    exactly where the detector's picture differs from reality.
    """
    return [
        {
            "id": "temperature",
            "label": "True room temperature",
            "unit": "°C",
            "source": TRUTH,
            "minimum": 18,
            "maximum": 120,
            "opacity": 0.75,
            "palette": ["#2563eb", "#22c55e", "#facc15", "#dc2626"],
            "values": {key: round(s.temperature, 2) for key, s in world.spaces.items()},
        },
        {
            "id": "smoke",
            "label": "True smoke obscuration",
            "unit": "1/m",
            "source": TRUTH,
            "minimum": 0,
            "maximum": 1.5,
            "opacity": 0.75,
            "palette": ["#0f172a", "#475569", "#cbd5f5", "#f8fafc"],
            "values": {key: round(s.smoke, 4) for key, s in world.spaces.items()},
        },
        {
            "id": "co",
            "label": "True CO concentration",
            "unit": "ppm",
            "source": TRUTH,
            "minimum": 0,
            "maximum": 1200,
            "opacity": 0.75,
            "palette": ["#22c55e", "#facc15", "#f97316", "#dc2626"],
            "values": {key: round(s.co, 1) for key, s in world.spaces.items()},
        },
        {
            "id": "p_fire",
            "label": "Detector P(fire)",
            "unit": "",
            "source": BELIEF,
            "minimum": 0,
            "maximum": 1,
            "opacity": 0.8,
            "palette": ["#1e293b", "#0ea5e9", "#f59e0b", "#dc2626"],
            "values": {key: round(value, 3) for key, value in probabilities.items()},
        },
    ]


SMOKE_THRESHOLD = 0.08  # below this there is nothing worth drawing
MAX_SMOKE_EFFECTS = 40  # particle systems are expensive in the viewer


def effects(world: World, burning: set[str]) -> list[dict]:
    """Fire, sprinkler and smoke particle effects for the 3D scene."""
    payload: list[dict] = []
    for key in burning:
        space = world.spaces[key]
        # Hotter fires are drawn bigger, clamped so a small one is still visible.
        intensity = min(1.0, max(0.2, (space.temperature - 20.0) / 120.0))
        payload.append(
            {
                "id": f"fire-{space.name}",
                "type": "fire",
                "label": f"Fire in {space.name}",
                "level": space.level,
                "room": space.name,
                "radius": 6,
                "height": 12,
                "intensity": round(intensity, 2),
            }
        )

    for space in world.spaces.values():
        if space.sprinkler:
            payload.append(
                {
                    "id": f"sprinkler-{space.name}",
                    "type": "sprinkler",
                    "level": space.level,
                    "room": space.name,
                    "radius": 5,
                    "height": 10,
                    "intensity": 0.9,
                }
            )

    smoky = sorted(
        (s for s in world.spaces.values() if s.smoke > SMOKE_THRESHOLD),
        key=lambda s: s.smoke,
        reverse=True,
    )
    # Only the smokiest rooms get an effect, or the viewer's frame rate collapses.
    for space in smoky[:MAX_SMOKE_EFFECTS]:
        payload.append(
            {
                "id": f"smoke-{space.name}",
                "type": "smoke",
                "level": space.level,
                "room": space.name,
                "radius": 8,
                "height": 16,
                "intensity": round(min(1.0, space.smoke), 2),
            }
        )
    return payload


STATE_COLOURS = {
    # state -> (colour, opacity). Redder and more solid means more serious.
    "CONFIRMED": ("#dc2626", 0.85),
    "SUPPRESSED": ("#dc2626", 0.6),
    "PRE_ALARM": ("#f97316", 0.7),
    "INVESTIGATING": ("#facc15", 0.5),
    "CLEARING": ("#22c55e", 0.4),
}


def highlights(world: World, states: dict[str, str]) -> list[dict]:
    """Outline every room the agent is currently worried about."""
    payload = []
    for key, state in states.items():
        space = world.spaces.get(key)
        colour = STATE_COLOURS.get(state)
        if space is None or colour is None:
            continue  # NORMAL rooms have no colour, so they are simply skipped
        payload.append(
            {
                "level": space.level,
                "room": space.name,
                "color": colour[0],
                "opacity": colour[1],
            }
        )
    return payload


SEVERITY = {
    # How loudly the viewer should announce each state.
    "INVESTIGATING": "info",
    "PRE_ALARM": "warning",
    "CONFIRMED": "critical",
    "SUPPRESSED": "critical",
    "CLEARING": "info",
}


def alerts(world: World, states: dict[str, str], probabilities: dict[str, float]) -> list[dict]:
    """One readable message per room in an alarm state."""
    payload = []
    for key, state in states.items():
        space = world.spaces.get(key)
        severity = SEVERITY.get(state)
        if space is None or severity is None:
            continue
        payload.append(
            {
                "id": f"alarm-{space.level}-{space.name}",
                "severity": severity,
                "title": f"{state.replace('_', ' ').title()} in {space.name}",
                "message": f"P(fire) {probabilities.get(key, 0.0):.0%}"
                + (", sprinkler active" if space.sprinkler else ""),
                "level": space.level,
                "room": space.name,
            }
        )
    return payload[:100]  # a wall of alerts helps nobody


MAX_ENTITIES = 2000  # the viewer will not draw more markers than this
EDGE_MARGIN = 0.05  # keeps rounding from pushing a clamped point back off the page


def _on_page(position: list[float], page: tuple[float, float] | None) -> tuple[float, float]:
    """Pull a point inside the floor drawing.

    People are scattered a little off the waypoint they are walking to, and near
    a door on the building's edge that scatter can land them off the page, which
    BuildSim rejects — taking the whole batch of occupants down with it.
    """
    x, y = round(position[0], 2), round(position[1], 2)
    if page is None:
        return x, y
    width, height = page
    return (
        min(max(x, EDGE_MARGIN), width - EDGE_MARGIN),
        min(max(y, EDGE_MARGIN), height - EDGE_MARGIN),
    )


def entities(
    world: World,
    people: list[Occupant],
    transition_ms: int,
    bounds: dict[str, tuple[float, float]] | None = None,
) -> list[dict]:
    """Everyone still inside. People who reached an exit have left the building."""
    payload = []
    for occupant in [p for p in people if not p.safe][:MAX_ENTITIES]:
        space = world.spaces.get(occupant.space)
        if space is None:
            continue
        x, y = _on_page(occupant.position, (bounds or {}).get(space.level))
        payload.append(
            {
                "id": occupant.id,
                "name": occupant.name,
                "type": occupant.figure,
                "level": space.level,
                "room": space.name,
                "position": [x, y],
                "status": occupant.status,
                # Tells the viewer to glide to the new spot rather than teleport.
                "transition_ms": transition_ms,
            }
        )
    return payload


def occupancy(world: World, people: list[Occupant]) -> dict:
    """Who is in which room. Used by the interlocks and shown in room labels."""
    rooms: dict[str, dict] = {}
    for occupant in people:
        if occupant.safe or occupant.space not in world.spaces:
            continue
        room = rooms.setdefault(occupant.space, {"persons": [], "aliens": []})
        room["persons"].append({"id": occupant.id, "name": occupant.name})
    return rooms


def doors(world: World, states: dict[str, str]) -> list[dict]:
    """The fire doors, one per room. Never locked, only open or closed."""
    payload = []
    for key, state in states.items():
        space = world.spaces.get(key)
        if space is None:
            continue
        payload.append(
            {
                "id": f"fire-door-{space.level}-{space.name}",
                "name": f"{space.name} fire door",
                "kind": "door",
                "level": space.level,
                "room": space.name,
                "state": state,
                "lock_state": "unlocked",
            }
        )
    return payload


EQUIPMENT_TYPES = {
    # our modality -> (BuildSim type, display label, unit)
    "smoke": ("smoke_detector", "Smoke detector", "1/m"),
    "co": ("co_sensor", "CO sensor", "ppm"),
    "temperature": ("temperature_sensor", "Temperature sensor", "°C"),
}


def equipment(world: World, devices: Iterable[Device]) -> list[dict]:
    """Mirror every sensing device into BuildSim's equipment tree."""
    payload = []
    for device in devices:
        space = world.spaces.get(device.space)
        if space is None:
            continue
        kind, label, unit = EQUIPMENT_TYPES[device.modality]
        payload.append(
            {
                "id": device.id,
                "name": f"{label} {space.name}",
                "type": kind,
                "category": "monitoring",
                "level": space.level,
                "room": space.name,
                "status": "running",
                "sensors": [
                    {
                        "id": f"{device.id}-val",
                        "name": label,
                        "type": device.modality,
                        "data_type": "text",
                        "unit": unit,
                        "value": "0",
                    }
                ],
                "actuators": [],
            }
        )
    return payload
