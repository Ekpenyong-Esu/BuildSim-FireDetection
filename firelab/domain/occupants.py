"""Occupants: where they are and how they follow a route. Pure.

Who they are lives in `roles.py`; this file is only about position and movement.
"""

from dataclasses import dataclass, field
from random import Random
from typing import Iterable

from .roles import ROLES
from .world import Space

MIN_ROOM_AREA = 8.0  # skip cupboards and shafts
PERSONAL_SPACE = 2.5  # floor-plan units of scatter, so people never share a point


@dataclass
class Occupant:
    """One person: where they are, where they are going, and whether they are out."""

    id: str  # "occ-<role>-<n>", e.g. "occ-student-3"; what BuildSim draws them under
    name: str  # "<Role> <n>", e.g. "Student 3"; shown on the marker in the viewer
    space: str  # key of the room they are in right now
    position: list[float]  # [x, y] on the plan, in plan units
    offset: tuple[float, float] = (0.0, 0.0)  # kept for life, so crowds do not stack
    route: list[list[float]] = field(default_factory=list)  # remaining waypoints
    route_spaces: list[str] = field(default_factory=list)  # the room at each waypoint
    status: str = "idle"  # "idle" | "evacuating" | "no route" (stranded) | "safe"
    safe: bool = False  # reached the last waypoint of their route: out of the building
    role: str = "staff"  # a key from roles.ROLES
    speed: float = 1.0  # their share of the configured walking speed
    figure: str = "man"  # which marker BuildSim draws
    fed: float = 0.0  # fraction of an incapacitating CO dose taken so far


def place(spaces: Iterable[Space], population: dict[str, int], rng: Random) -> list[Occupant]:
    """Scatter the given mix of people over the usable rooms.

    Rooms the walkable graph does not reach are skipped: nobody could ever be
    given a way out of them.
    """
    spaces = [s for s in spaces if s.routable]
    # Prefer proper rooms; fall back to anything at all rather than place nobody.
    rooms = [s for s in spaces if s.kind != "corridor" and s.area_m2 > MIN_ROOM_AREA] or spaces
    if not rooms:
        return []
    people = []
    for role in ROLES:
        for number in range(max(int(population.get(role.key, 0)), 0)):
            room = rng.choice(rooms)
            # A small permanent nudge off the room centre. Without it everyone who
            # reaches the same waypoint would be drawn on one spot.
            offset = (
                rng.uniform(-PERSONAL_SPACE, PERSONAL_SPACE),
                rng.uniform(-PERSONAL_SPACE, PERSONAL_SPACE),
            )
            people.append(
                Occupant(
                    id=f"occ-{role.key}-{number + 1}",
                    name=f"{role.singular} {number + 1}",
                    space=room.key,
                    position=[room.center[0] + offset[0], room.center[1] + offset[1]],
                    offset=offset,
                    role=role.key,
                    speed=role.speed,
                    figure=rng.choice(("man", "woman")),
                )
            )
    return people


def advance(occupant: Occupant, budget: float) -> None:
    """Walk `budget` floor-plan units along the route, consuming waypoints.

    `budget` is how far this person can move in one tick. They may pass several
    waypoints in one go, or fall short of the next one.
    """
    while budget > 0 and occupant.route:
        target = occupant.route[0]
        dx = target[0] - occupant.position[0]
        dy = target[1] - occupant.position[1]
        distance = (dx * dx + dy * dy) ** 0.5
        if distance <= budget:
            # Reached this waypoint: stand on it and take the next one.
            occupant.position = [target[0] + occupant.offset[0], target[1] + occupant.offset[1]]
            occupant.route.pop(0)
            if occupant.route_spaces:
                key = occupant.route_spaces.pop(0)
                if key:
                    occupant.space = key  # they are now in the next room
            budget -= distance
        else:
            # Out of steps for this tick: move part of the way and stop.
            occupant.position[0] += dx / distance * budget
            occupant.position[1] += dy / distance * budget
            budget = 0

    # No waypoints left means they reached the exit.
    if not occupant.route:
        occupant.safe = True
        occupant.status = "safe"
