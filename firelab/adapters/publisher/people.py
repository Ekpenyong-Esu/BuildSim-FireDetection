"""Where the occupants are: viewer markers and per-room occupancy."""

from ...domain.occupants import Occupant
from ...domain.world import World

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
