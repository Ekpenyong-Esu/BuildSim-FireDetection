"""Ignition sources and their multi-modal signatures.

Pure: standard library only. A source declares how much heat, smoke and CO it
contributes; the room dynamics in physics.py own every time constant.
"""

from dataclasses import dataclass
from math import exp

# Standard t-squared fire growth coefficients, kW/s^2.
ALPHA = {"slow": 0.0029, "medium": 0.0117, "fast": 0.0469, "ultrafast": 0.1876}

KINDS = (
    "flaming", # lots of heat, smoke, and CO.
    "smouldering", # little heat, dense smoke, and high CO.
    "cooking", # moderate heat and smoke, but little CO.
    "dust", # smoke alone, with no heat or CO.
    "steam" # steam-like particles, with no heat or CO.
    )


@dataclass(frozen=True)
class Source:
    """A scripted event. `kind` is also the ground-truth label."""

    id: str  # "src-<n>-<time lit>", e.g. "src-1-28800"; what the UI removes it by
    kind: str  # one of KINDS; "flaming" and "smouldering" are real fires, the rest nuisances
    space: str  # canonical "<level>/<name>" key
    t_start: float  # simulated seconds since midnight
    growth: str = "medium"  # a key of ALPHA; only a flaming fire uses it
    peak_kw: float = 2000.0  # a flaming fire stops growing here


def _bump(t: float, rise: float, fall: float) -> float:
    """Grow, hold, then fade away: the shape of a nuisance like toast or dust.

    A real fire keeps getting worse; these do not, which is the difference the
    detector has to learn.
    """
    if t <= 0:
        return 0.0
    return (1 - exp(-t / rise)) * exp(-max(0.0, t - 3 * rise) / fall)


def emission(source: Source, now: float) -> tuple[float, float, float]:
    """Return (heat_kW, smoke_equilibrium_1/m, co_equilibrium_ppm) at `now`.

    Equilibrium form keeps each source to a few lines and leaves the lag to the
    room. The CO-to-smoke ratio is what separates a fire from a nuisance.
    """
    e = now - source.t_start  # seconds since ignition
    if e <= 0:
        return 0.0, 0.0, 0.0  # not lit yet

    if source.kind == "flaming":
        # Heat grows with the square of time until it runs out of fuel.
        heat = min(ALPHA.get(source.growth, ALPHA["medium"]) * e * e, source.peak_kw)
        return heat, 0.06 * heat**0.5, 4.0 * heat**0.5

    if source.kind == "smouldering":
        # Barely any heat, dense smoke, very high CO: the hard case.
        ramp = 1 - exp(-e / 300)
        return 3.0 * ramp, 0.9 * ramp, 900.0 * ramp

    if source.kind == "cooking":
        # Warm and smoky, but hardly any CO: burnt toast, not a fire.
        ramp = _bump(e, 180, 900)
        return 12.0 * ramp, 0.35 * ramp, 25.0 * ramp

    if source.kind == "dust":
        # Smoke alone: no heat, no CO. A smoke detector on its own is fooled.
        return 0.0, 0.5 * _bump(e, 20, 120), 0.0

    if source.kind == "steam":
        return 0.0, 0.7 * _bump(e, 30, 200), 0.0

    return 0.0, 0.0, 0.0  # unknown kind: emit nothing
