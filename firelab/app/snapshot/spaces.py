"""The room table: for each watched room, the truth beside the reading."""

from ...domain import tenability
from ...domain.world import World


def rooms(world: World) -> list[dict]:
    """Every space, for the room picker. Small payload on purpose."""
    return [
        {"key": s.key, "level": s.level, "name": s.name, "kind": s.kind, "area": round(s.area_m2)}
        for s in sorted(world.spaces.values(), key=lambda s: (s.level, s.name))
    ]


def watched(engine) -> list[str]:
    """Rooms worth showing: monitored, burning, or suspected."""
    keys = set(engine.windows) | {s.space for s in engine.sources}
    keys |= {key for key, value in engine.probabilities.items() if value > 0.05}
    return sorted(keys)


def spaces(engine) -> list[dict]:
    """One row per watched room: the truth, the reading, and the verdict.

    `truth` and `reading` sit next to each other on purpose. The gap between
    them is what the whole exercise is about.
    """
    occupied: dict[str, int] = {}
    for occupant in engine.occupants:
        occupied[occupant.space] = occupied.get(occupant.space, 0) + 1

    rows = []
    for key in watched(engine):
        space = engine.world.spaces.get(key)
        if space is None:
            continue
        room_agent = engine.agents.get(key)
        features = engine.features.get(key)
        rows.append(
            {
                "key": key,
                "level": space.level,
                "name": space.name,
                "kind": space.kind,
                "truth": {
                    "temperature": round(space.temperature, 2),
                    "smoke": round(space.smoke, 4),
                    "co": round(space.co, 1),
                },
                "reading": {
                    "temperature": round(features.temperature, 2) if features else None,
                    "smoke": round(features.smoke, 4) if features else None,
                    "co": round(features.co, 1) if features else None,
                },
                "p_fire": round(engine.probabilities.get(key, 0.0), 3),
                # A room with no sensors has no opinion at all, not a calm one.
                "state": room_agent.state if room_agent else "UNMONITORED",
                "tenable": tenability.assess(space.temperature, space.smoke).tenable,
                "sprinkler": space.sprinkler,
                "door": engine.doors.get(key, "open"),
                "occupants": occupied.get(key, 0),
                "devices": [
                    {
                        "id": d.id,
                        "modality": d.modality,
                        "fault": d.fault,
                        "reading": round(d.reading, 3) if d.reading is not None else None,
                    }
                    for d in engine.devices.values()
                    if d.space == key
                ],
            }
        )
    return rows
