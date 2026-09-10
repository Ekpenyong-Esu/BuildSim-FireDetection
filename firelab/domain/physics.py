"""Lumped per-space fire physics over the building adjacency graph.

Pure: standard library only, no clock, no network. One `Space` per room or
corridor; heat, smoke and CO relax towards a source-driven equilibrium and
diffuse to neighbours across door-gated couplings.
"""

from dataclasses import dataclass, field
from math import exp

T_OUT = 20.0  # outdoor / baseline temperature, degrees C

# Time constants, in seconds: how sluggish each quantity is. After `tau` seconds
# a value has closed about 63% of the gap to where it is heading.
TAU_TEMP = 90.0
TAU_SMOKE = 45.0
TAU_CO = 60.0

# How readily each quantity leaks through a doorway into the next room.
DIFFUSION_SMOKE = 0.35
DIFFUSION_CO = 0.30
DIFFUSION_TEMP = 0.12

SPRINKLER_HRR_FACTOR = 0.25  # heat release surviving an active sprinkler
SPRINKLER_SMOKE_WASHOUT = 0.4
TEMP_GAIN = 140.0  # degrees C at 1 kW per cubic metre
TEMP_CEILING = 900.0  # post-flashover ceiling, degrees C above ambient


def approach(x: float, target: float, tau: float, dt: float) -> float:
    """Move `x` part of the way towards `target` over `dt` seconds.

    Nothing in a building changes instantly: a room warms up gradually rather
    than jumping to its final temperature. This one curve does all of it.
    """
    return target + (x - target) * exp(-dt / tau)


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


def step(world: World, emissions: dict[str, tuple[float, float, float]], dt: float) -> None:
    """Advance every space by `dt` seconds given this tick's source emissions.

    Two phases: first each room reacts to whatever is burning inside it, then
    neighbouring rooms trade some of what they have through the doorways.
    """
    for key, space in world.spaces.items():
        # Where this room is heading, given what is burning in it right now.
        heat, smoke_eq, co_eq = emissions.get(key, (0.0, 0.0, 0.0))
        if space.sprinkler:
            heat *= SPRINKLER_HRR_FACTOR
            smoke_eq *= SPRINKLER_SMOKE_WASHOUT

        # Sub-linear rise with heat density, capped at flashover temperatures.
        temp_target = T_OUT + min(TEMP_GAIN * (heat / space.volume_m3) ** (2 / 3), TEMP_CEILING)

        # Nothing jumps: each value eases towards its target at its own pace.
        space.temperature = approach(space.temperature, temp_target, TAU_TEMP, dt)
        space.smoke = approach(space.smoke, smoke_eq, TAU_SMOKE, dt)
        space.co = approach(space.co, co_eq, TAU_CO, dt)

    _diffuse(world, dt)


def _diffuse(world: World, dt: float) -> None:
    """Let neighbouring rooms even out, which is how smoke leaves the fire room."""
    # Work out every exchange first, apply them after, so the order of the
    # couplings cannot change the answer.
    deltas: dict[str, list[float]] = {key: [0.0, 0.0, 0.0] for key in world.spaces}
    for link in world.couplings:
        a = world.spaces.get(link.a)
        b = world.spaces.get(link.b)
        if a is None or b is None or link.openness <= 0.0:
            continue  # a shut door blocks the exchange entirely
        g = link.conductance * link.openness * dt
        for index, (attr, rate) in enumerate(
            (("temperature", DIFFUSION_TEMP), ("smoke", DIFFUSION_SMOKE), ("co", DIFFUSION_CO))
        ):
            # Flow always runs from the fuller room to the emptier one. The cap
            # stops a long time step from over-shooting past equal.
            flow = min(g * rate, 0.5) * (getattr(a, attr) - getattr(b, attr))
            deltas[a.key][index] -= flow
            deltas[b.key][index] += flow

    for key, (d_temp, d_smoke, d_co) in deltas.items():
        space = world.spaces[key]
        space.temperature = max(T_OUT, space.temperature + d_temp)
        space.smoke = max(0.0, space.smoke + d_smoke)
        space.co = max(0.0, space.co + d_co)
