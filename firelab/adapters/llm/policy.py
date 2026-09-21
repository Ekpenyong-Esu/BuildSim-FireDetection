"""When a room is worth asking the model about again.

Pure: a few numbers and three yes/no questions. Keeping the policy here means
the detector's scheduling can be tested with a fake clock and no endpoint, and
changed without touching the network code.
"""

from dataclasses import dataclass

from ...domain.features import Features


@dataclass(frozen=True)
class RefreshPolicy:
    """How often, and how long an answer stays good for. Simulated seconds."""

    every: float = 10.0  # do not ask about the same room more often than this
    max_age: float = 60.0  # after this, a verdict is stale and the rule takes over
    # A room below all three of these is quiet: nothing to ask about, so nothing
    # is spent on it. Set from the sensor noise floors in domain/sensing.py.
    quiet_smoke: float = 0.02  # 1/m
    quiet_co: float = 5.0  # ppm
    quiet_rise: float = 3.0  # degrees C above baseline


def is_quiet(policy: RefreshPolicy, features: Features) -> bool:
    """Nothing is happening in the room, as far as its sensors can tell."""
    return (
        features.smoke < policy.quiet_smoke
        and features.co < policy.quiet_co
        and features.temperature_rise < policy.quiet_rise
        and features.neighbour_agreement == 0.0
    )


def is_due(policy: RefreshPolicy, last_asked: float | None, now: float) -> bool:
    """Enough simulated time has passed since the room was last asked about."""
    return last_asked is None or now - last_asked >= policy.every


def is_fresh(policy: RefreshPolicy, verdict_at: float, now: float) -> bool:
    """The verdict is recent enough to act on."""
    return now - verdict_at <= policy.max_age
