"""Building hardware mirrored into BuildSim: fire doors and the equipment tree."""

from typing import Iterable

from ...domain.world import World
from ...domain.sensing import Device

EQUIPMENT_TYPES = {
    # our modality -> (BuildSim type, display label, unit)
    "smoke": ("smoke_detector", "Smoke detector", "1/m"),
    "co": ("co_sensor", "CO sensor", "ppm"),
    "temperature": ("temperature_sensor", "Temperature sensor", "°C"),
}


def doors(world: World, states: dict[str, str], danger: set[str] | None = None) -> list[dict]:
    """The fire doors, one per room. Never locked, only open or closed.

    A room we believe is alight is published with `blocked`. That flag is not
    decoration: BuildSim's walkable router drops the *entry* nodes of a blocked
    room, so it will not route anybody into a burning room.

    Note the limit, measured against the real building: it only bites on spaces
    that have entry nodes, which means rooms. Corridors have none — 41 of the
    305 named spaces on level0 — and an escape route is almost entirely
    corridor, so this does not by itself produce a detour around a burning
    corridor. `Evacuation._through_fire` is what still catches those.

    Every alarming room gets an entry even if no fire door was ever commanded
    there, because the routing matters whether or not the room has a door.
    """
    danger = danger or set()
    payload = []
    for key in sorted(set(states) | danger):
        space = world.spaces.get(key)
        if space is None:
            continue
        blocked = key in danger
        payload.append(
            {
                "id": f"fire-door-{space.level}-{space.name}",
                "name": f"{space.name} fire door",
                "kind": "door",
                "level": space.level,
                "room": space.name,
                # A blocked room is shown shut; otherwise whatever was commanded.
                "state": "blocked" if blocked else states.get(key, "open"),
                "lock_state": "unlocked",  # fire doors fail unlocked, always
                "blocked": blocked,
            }
        )
    return payload


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
