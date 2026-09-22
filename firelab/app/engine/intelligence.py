"""INTELLIGENCE: readings -> features -> P(fire) -> the room state machine.

Nothing in this file may touch `space.temperature`, `space.smoke` or `space.co`.
The truth is one attribute away and deliberately not used; keeping it in a file
of its own is what makes that restraint checkable rather than merely intended.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domain import agent as agent_mod
from ...domain.detector import FusionRule
from ...domain.features import extract

if TYPE_CHECKING:
    from .state import EngineState


def think(engine: EngineState) -> list[agent_mod.Command]:
    """Score every monitored room and step its agent.

    Returns the commands the agents want carried out; deciding and doing are
    kept apart so this stays testable without any actuators.
    """
    proposed: list[agent_mod.Command] = []
    neighbours = neighbour_readings(engine)
    for key, window in engine.windows.items():
        features = extract(window, neighbours.get(key, []))
        engine.features[key] = features
        probability = engine.detector.probability(features)
        journal_rule_verdict(engine, key, features, probability)
        engine.probabilities[key] = probability

        room_agent = engine.agents.setdefault(
            key, agent_mod.RoomAgent(space=key, since=engine.now)
        )
        before = room_agent.state
        commands = agent_mod.update(room_agent, probability, engine.now, thresholds(engine))
        if room_agent.state != before:
            name = engine.world.spaces[key].name
            engine.log("agent", f"{name}: {before} -> {room_agent.state}")
        if engine.config.response.auto:
            proposed.extend(commands)  # supervised mode drops them instead

    engine.score.update(
        engine.now,
        engine.sources,
        {key: a.state for key, a in engine.agents.items()},
        evacuating=sum(1 for o in engine.occupants if o.status == "evacuating"),
        inside=sum(1 for o in engine.occupants if not o.safe),
        adjacency=engine.world.adjacency(),
    )
    return proposed


# How much P(fire) has to move before the rule says so again. The model's lines
# use the same step, so the two detectors read alike in the journal.
JOURNAL_STEP = 0.1


def journal_rule_verdict(engine: EngineState, key: str, features, probability: float) -> None:
    """Write the rule's verdict to the journal when it changes materially.

    The model explains itself in the journal, so the rule does too: the same
    "says P(fire)=" line, followed by the terms that carried the score. A
    detector that journals its own verdicts is left to it.
    """
    if not isinstance(engine.detector, FusionRule):
        return
    previous = engine.probabilities.get(key)
    if not material_change(previous, probability, engine.config.response.investigate):
        return
    terms = engine.detector.explain(features)
    engine.log("detector", f"{key}: rule says P(fire)={probability:.2f}: {rule_summary(terms)}")


def material_change(previous: float | None, current: float, floor: float) -> bool:
    """Worth a line: the first time the score matters, and every step of JOURNAL_STEP after."""
    if current < floor and (previous is None or previous < floor):
        return False  # a quiet room stays quiet in the journal too
    if previous is None:
        return True
    return abs(current - previous) >= JOURNAL_STEP - 1e-9  # tolerate float rounding at exactly one step


def rule_summary(terms) -> str:
    """The three terms pushing hardest towards fire, as `name +weight`."""
    pushing = sorted((t for t in terms if t.name != "bias" and t.weighted > 0), key=lambda t: -t.weighted)
    if not pushing:
        return "nothing pushing towards fire"
    return ", ".join(f"{t.name.replace('_', ' ')} +{t.weighted:.1f}" for t in pushing[:3])


def thresholds(engine: EngineState) -> agent_mod.Thresholds:
    """Copy the live UI settings into the plain object the agent expects."""
    r = engine.config.response
    return agent_mod.Thresholds(
        investigate=r.investigate,
        pre_alarm=r.pre_alarm,
        confirm=r.confirm,
        clear=r.clear,
        dwell_pre_alarm=r.dwell_pre_alarm,
        dwell_confirm=r.dwell_confirm,
        dwell_clear=r.dwell_clear,
    )


def neighbour_readings(engine: EngineState) -> dict[str, list[float]]:
    """For each monitored room, the smoke its monitored neighbours report."""
    readings: dict[str, list[float]] = {}
    for link in engine.world.couplings:
        # Look at each doorway from both sides.
        for a, b in ((link.a, link.b), (link.b, link.a)):
            window = engine.windows.get(b)
            if window is None or a not in engine.windows:
                continue  # one side has no sensors, so it cannot corroborate
            readings.setdefault(a, []).append(window.latest("smoke"))
    return readings
