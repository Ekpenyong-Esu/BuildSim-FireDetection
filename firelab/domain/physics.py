"""Lumped per-space fire physics over the building adjacency graph.

Pure: standard library only, no clock, no network. Heat, smoke and CO relax
towards a source-driven equilibrium and diffuse to neighbours across door-gated
couplings. The rooms this runs on live in `world.py`.
"""

from math import exp

from .world import T_OUT, World

# Time constants, in seconds: how sluggish each quantity is. After `tau` seconds
# a value has closed about 63% of the gap to where it is heading.
TAU_TEMP = 90.0
TAU_SMOKE = 45.0
TAU_CO = 60.0

# How readily each quantity leaks through a doorway into the next room.
DIFFUSION_SMOKE = 0.35
DIFFUSION_CO = 0.30
DIFFUSION_TEMP = 0.12

# The most of the gap to its neighbours a room may close in one step, counting
# all its doorways together. Below 1.0 nothing can overshoot past equal, and no
# room can give away more than it holds however many doorways it has.
MAX_SHARE = 0.5

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
    """Let neighbouring rooms even out, which is how smoke leaves the fire room.

    The share of the gap a doorway closes in one step is capped, and then capped
    again across all of a room's doorways together. The second cap is the one
    that matters: a corridor has twenty doorways, and letting each move its own
    share of the gap independently means the corridor hands out several times
    what it holds. The shortfall used to vanish into the `max(0.0, ...)` below
    while every neighbour kept what it was given, so the building filled with
    smoke nobody produced — worse the faster the clock ran, because a longer
    step moves a larger share per doorway.
    """
    quantities = (("temperature", DIFFUSION_TEMP), ("smoke", DIFFUSION_SMOKE), ("co", DIFFUSION_CO))
    # Work out every exchange first, apply them after, so the order of the
    # couplings cannot change the answer.
    deltas: dict[str, list[float]] = {key: [0.0, 0.0, 0.0] for key in world.spaces}
    exchanges = []
    demand: dict[str, list[float]] = {key: [0.0, 0.0, 0.0] for key in world.spaces}
    for link in world.couplings:
        a = world.spaces.get(link.a)
        b = world.spaces.get(link.b)
        if a is None or b is None or link.openness <= 0.0:
            continue  # a shut door blocks the exchange entirely
        g = link.conductance * link.openness * dt
        # The share this one doorway would move, before its room's total is known.
        shares = [min(g * rate, MAX_SHARE) for _, rate in quantities]
        exchanges.append((a, b, shares))
        for index, share in enumerate(shares):
            demand[a.key][index] += share
            demand[b.key][index] += share

    for a, b, shares in exchanges:
        for index, (attr, _) in enumerate(quantities):
            # Scale the doorway back so neither room gives away more than
            # MAX_SHARE of what it holds across all its doorways together.
            busiest = max(demand[a.key][index], demand[b.key][index], MAX_SHARE)
            share = shares[index] * MAX_SHARE / busiest
            # Flow always runs from the fuller room to the emptier one.
            flow = share * (getattr(a, attr) - getattr(b, attr))
            deltas[a.key][index] -= flow
            deltas[b.key][index] += flow

    for key, (d_temp, d_smoke, d_co) in deltas.items():
        space = world.spaces[key]
        space.temperature = max(T_OUT, space.temperature + d_temp)
        space.smoke = max(0.0, space.smoke + d_smoke)
        space.co = max(0.0, space.co + d_co)
