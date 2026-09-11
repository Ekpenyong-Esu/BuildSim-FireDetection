"""ACTUATION: the single door between deciding and doing.

Agent commands and button presses both come through `apply`, so the interlocks
cannot be bypassed by clicking instead of waiting. A command the interlocks
refuse is not thrown away: the agent keeps offering it until it gets through.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domain import agent as agent_mod
from ...domain import interlocks

if TYPE_CHECKING:
    from .state import EngineState


def apply(
    engine: EngineState, cmd: agent_mod.Command, manual: bool = False
) -> interlocks.Verdict:
    """Check one command against the interlocks and, if allowed, carry it out."""
    space = engine.world.spaces.get(cmd.space)
    if space is None:
        return interlocks.Verdict(False, "unknown space")

    occupants = sum(1 for o in engine.occupants if o.space == cmd.space and not o.safe)
    on_route = any(cmd.space in o.route_spaces for o in engine.occupants)
    verdict = interlocks.check(cmd, space.temperature, occupants, on_route)
    held = (cmd.space, cmd.kind, cmd.value)
    if not verdict.allowed:
        # A held command is retried every tick, so only say so when the answer changes.
        if manual or engine.blocks.get(held) != verdict.reason:
            engine.log(
                "interlock", f"blocked {cmd.kind}={cmd.value} in {space.name}: {verdict.reason}"
            )
        engine.blocks[held] = verdict.reason
        return verdict
    engine.blocks.pop(held, None)

    if cmd.kind == "sprinkler":
        space.sprinkler = cmd.value == "on"
    elif cmd.kind == "fire_door":
        engine.doors[cmd.space] = cmd.value
        # A closed door does not seal: it still leaks about 15%.
        openness = 1.0 if cmd.value == "open" else 0.15
        for link in engine.world.couplings:
            if cmd.space in (link.a, link.b):
                link.openness = openness
    elif cmd.kind == "evacuate":
        # One room raises the alarm but the whole building walks out. Standing
        # down is different: nobody goes back inside while any room is still lit.
        if cmd.value == "start":
            for occupant in engine.occupants:
                if not occupant.safe:
                    occupant.status = "evacuating"
        elif not danger(engine):
            for occupant in engine.occupants:
                if not occupant.safe:
                    occupant.status = "idle"

    room_agent = engine.agents.get(cmd.space)
    if room_agent is not None:
        agent_mod.retire(room_agent, cmd)  # a human pressing the button settles it too
    prefix = "manual" if manual else "auto"
    engine.log("actuator", f"{prefix} {cmd.kind}={cmd.value} in {space.name}")
    engine.mark_dirty()
    return verdict


def override(engine: EngineState, kind: str, space: str, value: str) -> dict:
    """A human-issued command. It still has to pass the same interlocks."""
    cmd = agent_mod.Command(kind=kind, space=space, value=value, reason="manual override")
    verdict = apply(engine, cmd, manual=True)
    return {"allowed": verdict.allowed, "reason": verdict.reason}


def danger(engine: EngineState) -> set[str]:
    """Rooms people should be got out of. Pre-alarm counts: waiting costs lives."""
    return {
        key
        for key, room_agent in engine.agents.items()
        if room_agent.state in ("CONFIRMED", "SUPPRESSED", "PRE_ALARM")
    }
