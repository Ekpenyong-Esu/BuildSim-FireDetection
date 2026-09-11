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
