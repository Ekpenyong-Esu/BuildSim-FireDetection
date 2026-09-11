"""Turn BuildSim floor payloads into the pure `World` the physics runs on.

Spaces come from the room list; couplings come from the walkable graph, where
an edge between two nodes carrying different names is a physical opening
between those two spaces.
"""

from ..domain.world import UNITS_TO_METRES, Coupling, Space, World


def key_of(level: str, name: str) -> str:
    """The one identifier used for a room everywhere, e.g. "level1/2541"."""
    return f"{level}/{name}"


def page_bounds(floors: dict[str, dict]) -> dict[str, tuple[float, float]]:
    """Each level's drawing extent. BuildSim rejects any position outside it."""
    bounds = {}
    for level, payload in floors.items():
        page = payload.get("page") or {}
        width, height = float(page.get("width") or 0.0), float(page.get("height") or 0.0)
        if width > 0 and height > 0:
            bounds[level] = (width, height)
    return bounds


def build_world(floors: dict[str, dict]) -> tuple[World, dict[str, dict]]:
    """Return the world plus, per level, the entry-node -> room-name mapping."""
    world = World()
    entries: dict[str, dict] = {}

    for level, payload in floors.items():
        graph = payload.get("walkable_graph") or {}
        nodes = {node["id"]: node for node in graph.get("nodes", [])}

        world.spaces.update(_spaces_of(level, payload, nodes))
        world.couplings.extend(_couplings_of(level, graph, nodes, world.spaces))
        # Doorways to the outside world, used later as evacuation targets.
        entries[level] = {
            node_id: node.get("name")
            for node_id, node in nodes.items()
            if node.get("type") == "entry"
        }

    return world, entries


def _spaces_of(level: str, payload: dict, nodes: dict) -> dict[str, Space]:
    """One `Space` per named room on this level."""
    # Rooms the walkable graph actually reaches. A few have no node at all.
    routable = {node.get("name") for node in nodes.values() if node.get("name")}
    spaces = {}
    for room in payload.get("rooms", []):
        name = room.get("name")
        if not name:
            continue
        center = room.get("center") or [0.0, 0.0]
        key = key_of(level, name)
        spaces[key] = Space(
            key=key,
            level=level,
            name=name,
            kind=(room.get("type") or "room").lower(),
            # Floor plans are in half-metre units, so areas need squaring.
            area_m2=float(room.get("area") or 0.0) * UNITS_TO_METRES**2,
            center=(float(center[0]), float(center[1])),
            routable=name in routable,
        )
    return spaces


def _couplings_of(
    level: str, graph: dict, nodes: dict, spaces: dict[str, Space]
) -> list[Coupling]:
    """Every doorway on this level, derived from the walkable graph's edges.

    An edge joining two differently named nodes is an opening between two rooms.
    That is how smoke gets from one to the other.
    """
    seen: dict[tuple[str, str], float] = {}
    for edge in graph.get("edges", []):
        a = nodes.get(edge.get("from"))
        b = nodes.get(edge.get("to"))
        if not a or not b:
            continue
        name_a, name_b = a.get("name"), b.get("name")
        if not name_a or not name_b or name_a == name_b:
            continue  # an edge inside a single room is not a doorway
        key_a, key_b = key_of(level, name_a), key_of(level, name_b)
        if key_a not in spaces or key_b not in spaces:
            continue
        # Ordered, so A-B and B-A land on the same entry.
        pair = (key_a, key_b) if key_a < key_b else (key_b, key_a)
        weight = max(float(edge.get("weight") or 1.0), 1.0)
        conductance = 1.0 / weight  # a short edge is a wide opening
        seen[pair] = max(seen.get(pair, 0.0), conductance)

    return [Coupling(a=a, b=b, conductance=c) for (a, b), c in seen.items()]
