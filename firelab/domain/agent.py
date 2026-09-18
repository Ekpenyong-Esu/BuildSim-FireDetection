"""The alarm state machine: NORMAL -> INVESTIGATING -> PRE_ALARM -> CONFIRMED -> SUPPRESSED.

The agent issues commands. It never writes actuator state, and it never sees
the truth - only P(fire) from the detector. A command it asks for stays asked
for until it is carried out, because an interlock saying "not yet" is a delay
and not a refusal.
"""

from dataclasses import dataclass, field

STATES = ("NORMAL", "INVESTIGATING", "PRE_ALARM", "CONFIRMED", "SUPPRESSED", "CLEARING")


@dataclass
class Thresholds:
    """The trigger levels, and how long P(fire) must hold there before acting.

    The waiting periods (the dwells) are what stop a flickering sensor from
    opening and closing fire doors all day.
    """

    # P(fire) levels, 0..1
    investigate: float = 0.35  # NORMAL -> INVESTIGATING: start watching
    pre_alarm: float = 0.55  # INVESTIGATING -> PRE_ALARM, once held for dwell_pre_alarm
    confirm: float = 0.75  # PRE_ALARM -> CONFIRMED, once PRE_ALARM has lasted dwell_confirm
    clear: float = 0.25  # at or below this for dwell_clear: stand down
    # how long, in simulated seconds, a level must hold before the step is taken
    dwell_pre_alarm: float = 20.0
    dwell_confirm: float = 25.0
    dwell_clear: float = 90.0


@dataclass
class Command:
    """A request to change something physical. Still has to pass the interlocks."""

    kind: str  # "sprinkler" | "fire_door" | "evacuate"
    space: str  # key of the room it is about
    value: str  # "on"/"off", "open"/"closed"/"locked", or "start"/"stop"
    reason: str  # why the agent asked, in words; shown in the journal


@dataclass
class RoomAgent:
    """One room's opinion of itself: its state and how long it has been there."""

    space: str  # key of the room this agent watches
    state: str = "NORMAL"  # one of STATES
    probability: float = 0.0  # the latest P(fire) the detector gave this room
    since: float = 0.0  # when the current state was entered
    above_since: float | None = None  # when P(fire) first went above pre_alarm
    below_since: float | None = None  # when it first went below clear
    under_since: float | None = None  # when it first fell back under confirm
    # Commands asked for but not yet carried out. An interlock that says "not
    # yet" must not become "never", so a request stands until it is honoured.
    pending: list[Command] = field(default_factory=list)
    suppressing: bool = False  # a sprinkler this agent asked for is running


def update(
    agent: RoomAgent, probability: float, now: float, thresholds: Thresholds
) -> list[Command]:
    """Advance one room's state machine and return the commands it wants issued."""
    agent.probability = probability

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
    if probability < thresholds.confirm:
        agent.under_since = agent.under_since if agent.under_since is not None else now
    else:
        agent.under_since = None

    previous = agent.state

    # One step at a time, and only ever to a neighbouring state.
    if agent.state in ("NORMAL", "CLEARING"):
        if probability >= thresholds.investigate:
            agent.state = "INVESTIGATING"
        elif agent.state == "CLEARING" and now - agent.since >= thresholds.dwell_clear:
            # Quiet ever since it stood down, so stop flagging the room as an incident.
            agent.state = "NORMAL"
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
    elif agent.state == "CONFIRMED":
        # Standing down takes much longer than raising the alarm did.
        if agent.below_since is not None and now - agent.below_since >= thresholds.dwell_clear:
            agent.state = "CLEARING"
        elif (
            agent.suppressing
            and agent.under_since is not None
            and now - agent.under_since >= thresholds.dwell_confirm
        ):
            # Water has been on the fire and the evidence has stayed down for as
            # long as it took to confirm: the fire is being held, not out.
            agent.state = "SUPPRESSED"
    elif agent.state == "SUPPRESSED":
        if agent.below_since is not None and now - agent.below_since >= thresholds.dwell_clear:
            agent.state = "CLEARING"
        elif probability >= thresholds.confirm:
            agent.state = "CONFIRMED"  # burning on through the water

    if agent.state != previous:
        agent.since = now
        # SUPPRESSED is still an alarm, so CONFIRMED's outstanding requests stand.
        if agent.state != "SUPPRESSED":
            agent.pending = _on_enter(agent)

    # Anything the interlocks deferred is offered again on every tick.
    return list(agent.pending)


def retire(agent: RoomAgent, command: Command) -> None:
    """Note that a command was carried out, so it stops being asked for."""
    agent.pending = [c for c in agent.pending if c.kind != command.kind]
    if command.kind == "sprinkler":
        agent.suppressing = command.value == "on"


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
