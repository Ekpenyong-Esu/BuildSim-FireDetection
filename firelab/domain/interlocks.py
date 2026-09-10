"""Safety rules the agent cannot override.

They live here, not in the agent, so a buggy or mistrained agent still cannot
trap anyone or flood a dry room.
"""

from dataclasses import dataclass

from .agent import Command


@dataclass
class Verdict:
    """Yes or no, plus a reason plain enough to show to an operator."""

    allowed: bool
    reason: str


def check(
    command: Command,
    temperature: float,
    occupants: int,
    on_escape_route: bool,
) -> Verdict:
    """Validate one command against the interlocks.

    Every command passes through here, whether the agent proposed it or a person
    clicked it. There is no way round.
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

    return Verdict(True, "no interlock applies")
