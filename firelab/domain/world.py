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
    """A room or a corridor: the unit the physics is solved on."""

    key: str
    level: str
    name: str
    kind: str  # "room" or "corridor"
    area_m2: float
    center: tuple[float, float]
    routable: bool = True  # false when the walkable graph has no node for it
    temperature: float = T_OUT
    smoke: float = 0.0
    co: float = 0.0
    sprinkler: bool = False

    @property
    def volume_m3(self) -> float:
        """Floor area times a 3 m ceiling. Big rooms dilute a fire, small ones do not."""
        return max(self.area_m2 * 3.0, 10.0)


@dataclass
class Coupling:
    """A door-gated path between two spaces; `openness` is 0..1."""

    a: str
    b: str
    conductance: float
    openness: float = 1.0


@dataclass
class World:
    """Every room, plus the openings between them. The complete state of reality."""

    spaces: dict[str, Space] = field(default_factory=dict)
    couplings: list[Coupling] = field(default_factory=list)

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
