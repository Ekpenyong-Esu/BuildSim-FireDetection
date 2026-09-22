"""Check commands before they can change the simulated building.

The engine sends both automatic and manual commands through ``check``. Only
allowed commands reach the building, and blocked commands are recorded.

They live here, not in the agent, so a buggy or mistrained agent still cannot
trap anyone or flood a dry room.
"""

from dataclasses import dataclass

from .agent import Command


@dataclass
class Verdict:
    """Yes or no, plus a reason plain enough to show to an operator."""

    allowed: bool  # False means the command is refused this tick
    reason: str  # why, e.g. "fire doors fail unlocked"; "" when allowed


def check(
    command: Command,
    temperature: float,
    occupants: int,
    on_escape_route: bool,
    neighbours_alarming: int = 0,
) -> Verdict:
    """Validate one command against the interlocks.

    Every command passes through here, whether the agent proposed it or a person
    clicked it. There is no way round. `neighbours_alarming` is how many rooms
    next door are still in an alarm state; standing down beside one is refused.
    """
    if command.kind == "sprinkler" and command.value == "on":
        # Smoke on its own is not enough to soak a room: burnt toast would do it.
        if temperature < 35.0:
            return Verdict(False, "no heat corroboration: smoke alone does not release water")
        return Verdict(True, "heat corroborated")

    if command.kind == "fire_door" and command.value in ("closed", "locked"):
        if command.value == "locked":
            return Verdict(False, "fire doors fail unlocked")  # never trap anyone
        # Holding smoke back matters less than letting people out.
        if on_escape_route:
            return Verdict(False, "space is on an active escape route")
        if occupants > 0:
            return Verdict(False, f"{occupants} occupant(s) still inside")
        return Verdict(True, "compartment empty and off-route")

    if command.kind in ("sprinkler", "fire_door") and command.value in ("off", "open"):
        # A room next to a fire that is still burning does not get to reopen its
        # door and switch its water off on its own evidence: its own sprinkler is
        # what made its readings look safe, and the danger next door has not moved.
        if neighbours_alarming > 0:
            return Verdict(False, f"{neighbours_alarming} neighbouring room(s) still alarming: not standing down")
        return Verdict(True, "no fire next door")

    return Verdict(True, "no interlock applies")
