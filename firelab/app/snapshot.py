"""Build the JSON the UI reads. Reads engine state, never changes it."""

from ..domain import occupants
from ..domain import tenability
from ..domain.physics import World


def rooms(world: World) -> list[dict]:
    """Every space, for the room picker. Small payload on purpose."""
    return [
        {"key": s.key, "level": s.level, "name": s.name, "kind": s.kind, "area": round(s.area_m2)}
        for s in sorted(world.spaces.values(), key=lambda s: (s.level, s.name))
    ]


def build(engine) -> dict:
    """A full picture of the simulation, small enough to push every tick.

    This one dictionary is the entire contract with the UI. Nothing in the
    browser reaches past it into the engine.
    """
    return {
        "clock": _clock(engine),
        "buildsim": _buildsim(engine),
        "detector": engine.detector.name,
        "auto": engine.config.response.auto,
        "spaces": _spaces(engine),
        "sources": [dict(s.__dict__) for s in engine.sources],
        "counts": _counts(engine),
        "population": _population(engine),
        "tenability": _tenability(engine),
        "score": engine.score.summary(),
        "evacuation": _evacuation(engine),
        "journal": engine.journal[-40:],  # the newest entries only
    }


def _clock(engine) -> dict:
    """Simulated time, both as a number and as a readable hh:mm:ss."""
    hours, remainder = divmod(int(engine.now) % 86400, 3600)  # wrap at midnight
    minutes, seconds = divmod(remainder, 60)
    return {
        "seconds": round(engine.now, 1),
        "text": f"{hours:02d}:{minutes:02d}:{seconds:02d}",
        "running": engine.running,
        "factor": engine.config.factor,
    }


def _buildsim(engine) -> dict:
    """Whether the 3D viewer is reachable and how much of it has been loaded."""
    return {
        "url": engine.config.buildsim_url,
        "connected": engine.connected,
        "loaded": engine.loaded,
        "levels": list(engine.floors),
        "spaces": len(engine.world.spaces),
    }


def _watched(engine) -> list[str]:
    """Rooms worth showing: monitored, burning, or suspected."""
    keys = set(engine.windows) | {s.space for s in engine.sources}
    keys |= {key for key, value in engine.probabilities.items() if value > 0.05}
    return sorted(keys)


def _spaces(engine) -> list[dict]:
    """One row per watched room: the truth, the reading, and the verdict.

    `truth` and `reading` sit next to each other on purpose. The gap between
    them is what the whole exercise is about.
    """
    occupied: dict[str, int] = {}
    for occupant in engine.occupants:
        occupied[occupant.space] = occupied.get(occupant.space, 0) + 1

    rows = []
    for key in _watched(engine):
        space = engine.world.spaces.get(key)
        if space is None:
            continue
        room_agent = engine.agents.get(key)
        features = engine.features.get(key)
        rows.append(
            {
                "key": key,
                "level": space.level,
                "name": space.name,
                "kind": space.kind,
                "truth": {
                    "temperature": round(space.temperature, 2),
                    "smoke": round(space.smoke, 4),
                    "co": round(space.co, 1),
                },
                "reading": {
                    "temperature": round(features.temperature, 2) if features else None,
                    "smoke": round(features.smoke, 4) if features else None,
                    "co": round(features.co, 1) if features else None,
                },
                "p_fire": round(engine.probabilities.get(key, 0.0), 3),
                # A room with no sensors has no opinion at all, not a calm one.
                "state": room_agent.state if room_agent else "UNMONITORED",
                "tenable": tenability.assess(space.temperature, space.smoke).tenable,
                "sprinkler": space.sprinkler,
                "door": engine.doors.get(key, "open"),
                "occupants": occupied.get(key, 0),
                "devices": [
                    {
                        "id": d.id,
                        "modality": d.modality,
                        "fault": d.fault,
                        "reading": round(d.reading, 3) if d.reading is not None else None,
                    }
                    for d in engine.devices.values()
                    if d.space == key
                ],
            }
        )
    return rows


def _counts(engine) -> dict:
    """The headline numbers along the top of the UI."""
    return {
        "devices": len(engine.devices),
        "faulty": sum(1 for d in engine.devices.values() if d.fault != "none"),
        "alarms": sum(
            1 for a in engine.agents.values() if a.state in ("CONFIRMED", "SUPPRESSED")
        ),
        "evacuating": sum(1 for o in engine.occupants if o.status == "evacuating"),
        "safe": sum(1 for o in engine.occupants if o.safe),
        "occupants": len(engine.occupants),
    }


def _tenability(engine) -> dict:
    """Life safety: which rooms have stopped being escapable, and who is in them.

    This is the number the whole system exists to keep at zero. Detection
    latency only matters through its effect on it.
    """
    rooms = []
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


def _population(engine) -> list[dict]:
    """How each role is getting on. Visitors are expected to lag the students."""
    rows = []
    for role in occupants.ROLES:
        people = [o for o in engine.occupants if o.role == role.key]
        if not people:
            continue
        rows.append(
            {
                "key": role.key,
                "label": role.label,
                "note": role.note,
                "speed": role.speed,
                "total": len(people),
                "safe": sum(1 for o in people if o.safe),
                "evacuating": sum(1 for o in people if o.status == "evacuating"),
                "stranded": sum(1 for o in people if o.status == "no route"),
            }
        )
    return rows


def why(engine, space: str) -> list[dict]:
    """What pushed P(fire) where it is. Asked for one room at a time: sending it
    for all 956 would nearly double every snapshot."""
    features = engine.features.get(space)
    if features is None:
        return []
    return [
        {"name": term.name, "value": round(term.value, 4), "weighted": round(term.weighted, 3)}
        for term in engine.detector.explain(features)
    ]


def _evacuation(engine) -> dict:
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
