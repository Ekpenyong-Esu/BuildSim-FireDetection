"""The building as the physics sees it: rooms, doorways, and the state in each.

These are the nouns the rest of the project shares. Ten modules import `World`
or `Space` without ever running the solver, which is why they live here and not
in `physics.py`.
"""

from dataclasses import dataclass, field

T_OUT = 20.0  # outdoor / baseline temperature, degrees C
# Floor plans are drawn in units of 0.5 m. Every distance in the project is in
# those units; this is the one place that says what they mean.
UNITS_TO_METRES = 0.5


@dataclass
class Space:
    """A room or a corridor: the unit the physics is solved on.

    The first three fields name the room twice on purpose. `level` and `name`
    are how BuildSim addresses it. `key` is how firelab does: the two joined
    as "level0/A1016", because a name alone is not unique (there is an A1123
    on level0 and another on level1). Everything firelab keeps per room, from
    `World.spaces` to the danger set to a person's `space`, is keyed by it.
    """

    key: str  # "level/name", unique across the building; the dict key everywhere
    level: str  # which storey, e.g. "level0"; what BuildSim calls the floor
    name: str  # the room's name on the plan, e.g. "A1016"; unique only per storey
    kind: str  # "room" or "corridor"; corridors get no occupants placed in them
    area_m2: float  # floor area, converted from the plan's half-metre units
    center: tuple[float, float]  # where on the plan, in plan units; used for drawing
    routable: bool = True  # false when the walkable graph has no node for it
    # The state that the physics changes every step: what is really in the room.
    temperature: float = T_OUT  # degrees C
    smoke: float = 0.0  # obscuration, 1/m
    co: float = 0.0  # ppm
    sprinkler: bool = False  # on: physics cuts the heat to 25 % and the smoke to 40 %

    @property
    def volume_m3(self) -> float:
        """Floor area times a 3 m ceiling. Big rooms dilute a fire, small ones do not."""
        return max(self.area_m2 * 3.0, 10.0)


@dataclass
class Coupling:
    """A door-gated path between two spaces; `openness` is 0..1.

    Heat, smoke and CO leak from one side to the other in proportion to
    `conductance × openness`. Every walkable link between two different rooms
    on the plan becomes one of these, and so does every stairwell.
    """

    a: str  # key of the room on one side, e.g. "level0/A1016"
    b: str  # key of the room on the other side
    conductance: float  # how wide the opening is: 1 / link weight, or 0.6 for a stairwell
    openness: float = 1.0  # 1.0 open; a closed fire door sets it to 0.15 on every doorway of that room


@dataclass
class World:
    """Every room, plus the openings between them. The complete state of reality."""

    spaces: dict[str, Space] = field(default_factory=dict)  # every room, by its key
    couplings: list[Coupling] = field(default_factory=list)  # every doorway and stairwell

    def reset(self) -> None:
        """Put the whole building back to a cold, clean, quiet start."""
        for space in self.spaces.values():
            space.temperature = T_OUT
            space.smoke = 0.0
            space.co = 0.0
            space.sprinkler = False
        for coupling in self.couplings:
            # A door shut by the last run would otherwise still be throttling
            # smoke to 15% in the next one, with nothing in the UI to show it.
            coupling.openness = 1.0

    def adjacency(self) -> dict[str, set[str]]:
        """Which spaces share a doorway with which. Smoke travels along these."""
        links: dict[str, set[str]] = {}
        for coupling in self.couplings:
            links.setdefault(coupling.a, set()).add(coupling.b)
            links.setdefault(coupling.b, set()).add(coupling.a)
        return links
