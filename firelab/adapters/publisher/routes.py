"""Escape routes in BuildSim's shape.

BuildSim draws a route as a list of waypoints plus a distance, and it wants that
distance in metres while the floor plan is in 0.5 m units.
"""

from ..buildsim import UNITS_TO_METRES


def path_length(path: list[dict]) -> float:
    """Total walking distance of a route: add up the gaps between waypoints."""
    return sum(
        ((b["x"] - a["x"]) ** 2 + (b["y"] - a["y"]) ** 2) ** 0.5
        for a, b in zip(path, path[1:])
    )


def route(path: list[dict]) -> dict:
    """A route in BuildSim's shape, with the distance converted to metres."""
    return {"path": path, "distance": round(path_length(path) * UNITS_TO_METRES, 1)}
