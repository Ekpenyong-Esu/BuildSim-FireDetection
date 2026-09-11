"""Escape routes in BuildSim's shape.

BuildSim draws a route as a list of waypoints plus a distance, and it wants that
distance in metres while the floor plan is in 0.5 m units.
"""

from ...domain.world import UNITS_TO_METRES


def path_length(path: list[dict]) -> float:
    """Total walking distance of a route: add up the gaps between waypoints."""
    return sum(
        ((b["x"] - a["x"]) ** 2 + (b["y"] - a["y"]) ** 2) ** 0.5
        for a, b in zip(path, path[1:])
    )


def route(path: list[dict], level: str = "") -> dict:
    """A route in BuildSim's shape, with the distance converted to metres.

    Each node carries the storey it is on. A single-floor route comes back from
    BuildSim without one, and the viewer then guesses the floor from the first
    room name and falls back to level1 — which drew a ground-floor escape two
    storeys up. We know the level, so we say it.
    """
    nodes = [{**node, "level": level} for node in path] if level else path
    return {"path": nodes, "distance": round(path_length(path) * UNITS_TO_METRES, 1)}
