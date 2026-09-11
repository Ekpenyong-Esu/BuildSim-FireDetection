"""Life safety: where the building has stopped being escapable, and who is still in it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domain import tenability

if TYPE_CHECKING:
    from ..engine.state import EngineState


def tenability_report(engine: EngineState) -> dict:
    """Which rooms have stopped being escapable, and who is in them.

    This is the number the whole system exists to keep at zero. Detection
    latency only matters through its effect on it.
    """
    rooms: list[dict] = []
    heads: dict[str, int] = {}
    for occupant in engine.occupants:
        if not occupant.safe:
            heads[occupant.space] = heads.get(occupant.space, 0) + 1

    for key, space in engine.world.spaces.items():
        verdict = tenability.assess(space.temperature, space.smoke)
        if verdict.tenable:
            continue
        rooms.append(
            {
                "key": key,
                "level": space.level,
                "name": space.name,
                "reason": verdict.reason,
                "occupants": heads.get(key, 0),
            }
        )
    # Worst first: the rooms with people in them are the ones to look at.
    rooms.sort(key=lambda r: -r["occupants"])

    return {
        "untenable_rooms": rooms[:12],
        "untenable_count": len(rooms),
        "exposed": sum(r["occupants"] for r in rooms),
        # Counted over everyone, not just those still inside: reaching the door
        # having breathed an incapacitating dose on the way is not a success.
        "incapacitated": sum(1 for o in engine.occupants if o.fed >= tenability.FED_LIMIT),
        "worst_fed": round(max((o.fed for o in engine.occupants), default=0.0), 3),
        "fed_limit": tenability.FED_LIMIT,
    }


def evacuation(engine: EngineState) -> dict:
    """Who is still inside, per floor, and who could not be given a route."""
    levels: dict[str, dict[str, int]] = {}
    stranded = []
    for occupant in engine.occupants:
        level = occupant.space.split("/")[0]
        row = levels.setdefault(level, {"inside": 0, "evacuating": 0, "safe": 0, "stranded": 0})
        if occupant.safe:
            row["safe"] += 1
            continue
        row["inside"] += 1
        if occupant.status == "evacuating":
            row["evacuating"] += 1
        elif occupant.status == "no route":
            row["stranded"] += 1
            space = engine.world.spaces.get(occupant.space)
            stranded.append({"id": occupant.id, "room": space.name if space else occupant.space})
    return {
        "levels": [{"level": level, **row} for level, row in sorted(levels.items())],
        "stranded": stranded[:12],
    }
