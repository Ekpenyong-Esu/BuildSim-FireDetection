"""The alarm state machine: NORMAL -> INVESTIGATING -> PRE_ALARM -> CONFIRMED -> SUPPRESSED.

The agent issues commands. It never writes actuator state, and it never sees
the truth - only P(fire) from the detector.
"""

from dataclasses import dataclass, field

STATES = ("NORMAL", "INVESTIGATING", "PRE_ALARM", "CONFIRMED", "SUPPRESSED", "CLEARING")


@dataclass
class Thresholds:
    """The trigger levels, and how long P(fire) must hold there before acting.

    The waiting periods (the dwells) are what stop a flickering sensor from
    opening and closing fire doors all day.
    """

    investigate: float = 0.35
    pre_alarm: float = 0.55
    confirm: float = 0.75
    clear: float = 0.25
    dwell_pre_alarm: float = 20.0
    dwell_confirm: float = 25.0
    dwell_clear: float = 90.0


@dataclass
class Command:
    """A request to change something physical. Still has to pass the interlocks."""

    kind: str  # "sprinkler" | "fire_door" | "evacuate"
    space: str
    value: str
    reason: str


@dataclass
class RoomAgent:
    """One room's opinion of itself: its state and how long it has been there."""

    space: str
    state: str = "NORMAL"
    probability: float = 0.0
    since: float = 0.0  # when the current state was entered
    above_since: float | None = None  # when P(fire) first went above pre_alarm
    below_since: float | None = None  # when it first went below clear


def update(
    agent: RoomAgent, probability: float, now: float, thresholds: Thresholds
) -> list[Command]:
    """Advance one room's state machine and return the commands it wants issued."""
    agent.probability = probability
    commands: list[Command] = []

    # Keep track of how long the probability has been high, and how long low.
    # Setting the timestamp to None resets the stopwatch.
    if probability >= thresholds.pre_alarm:
        agent.above_since = agent.above_since if agent.above_since is not None else now
    else:
        agent.above_since = None
    if probability <= thresholds.clear:
        agent.below_since = agent.below_since if agent.below_since is not None else now
    else:
        agent.below_since = None

    previous = agent.state

    # One step at a time, and only ever to a neighbouring state.
    if agent.state in ("NORMAL", "CLEARING"):
        if probability >= thresholds.investigate:
            agent.state = "INVESTIGATING"
    elif agent.state == "INVESTIGATING":
        if agent.above_since is not None and now - agent.above_since >= thresholds.dwell_pre_alarm:
            agent.state = "PRE_ALARM"
        elif probability < thresholds.clear:
            agent.state = "NORMAL"
    elif agent.state == "PRE_ALARM":
        if probability >= thresholds.confirm and now - agent.since >= thresholds.dwell_confirm:
            agent.state = "CONFIRMED"
        elif probability < thresholds.investigate:
            agent.state = "INVESTIGATING"
    elif agent.state in ("CONFIRMED", "SUPPRESSED"):
        # Standing down takes much longer than raising the alarm did.
        if agent.below_since is not None and now - agent.below_since >= thresholds.dwell_clear:
            agent.state = "CLEARING"

    # Commands are only produced at the moment a room changes state.
    if agent.state != previous:
        agent.since = now
        commands = _on_enter(agent)

    return commands


def _on_enter(agent: RoomAgent) -> list[Command]:
    """What to ask for on arriving in a state. Only two states ask for anything."""
    reason = f"P(fire)={agent.probability:.2f} in {agent.space}"
    if agent.state == "CONFIRMED":
        return [
            Command("sprinkler", agent.space, "on", reason),
            Command("fire_door", agent.space, "closed", reason),
            Command("evacuate", agent.space, "start", reason),
        ]
    if agent.state == "CLEARING":
        return [
            Command("sprinkler", agent.space, "off", reason),
            Command("fire_door", agent.space, "open", reason),
            Command("evacuate", agent.space, "stop", reason),
        ]
    return []
