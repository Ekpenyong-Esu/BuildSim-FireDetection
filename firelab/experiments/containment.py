"""Does the response actually contain the fire? Three runs of the same office fire:
no response at all, the full autonomous response, and the sprinkler alone (the
fire door re-opened by hand as soon as the agent shuts it).

    cd firelab && .venv/bin/python experiments/containment.py
"""

import asyncio
import json
import sys
from pathlib import Path

# Runnable from anywhere: put the repository root (the parent of `firelab/`) on
# the path so `firelab.*` imports resolve even when started as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from firelab.app.engine import actuation, scenario, session
from firelab.domain import tenability
from firelab.experiments.run_experiments import ROOM, STEP, fresh

OUT = Path(__file__).resolve().parent / "results"


async def contain(mode: str) -> dict:
    engine = await fresh(auto=(mode != "none"))
    session.reset(engine)
    t0 = engine.now
    scenario.apply_preset(engine, "office-fire", ROOM)
    neighbours = scenario.neighbours_of(engine, ROOM)
    lost: set[str] = set()
    peaks = {k: [20.0, 0.0] for k in [ROOM, *neighbours]}
    door_reopened = None
    for _ in range(int(20 * 60 / STEP)):
        await engine._tick(STEP)
        if mode == "sprinkler-only" and engine.doors.get(ROOM) == "closed":
            actuation.override(engine, "fire_door", ROOM, "open")
            door_reopened = door_reopened or round(engine.now - t0)
        for key, space in engine.world.spaces.items():
            if not tenability.assess(space.temperature, space.smoke).tenable:
                lost.add(key)
            if key in peaks:
                peaks[key][0] = max(peaks[key][0], space.temperature)
                peaks[key][1] = max(peaks[key][1], space.smoke)
    score = engine.score.summary()
    return {
        "mode": mode, "rooms_lost": len(lost),
        "lost_on_other_floors": sum(1 for k in lost if not k.startswith(ROOM.split('/')[0])),
        "fire_room_peak_temp": round(peaks[ROOM][0], 1), "fire_room_peak_smoke": round(peaks[ROOM][1], 3),
        "neighbour_peak_temp": round(max(v[0] for k, v in peaks.items() if k != ROOM), 1),
        "neighbour_peak_smoke": round(max(v[1] for k, v in peaks.items() if k != ROOM), 3),
        "sprinkler": engine.world.spaces[ROOM].sprinkler, "door": engine.doors.get(ROOM, "open"),
        "door_reopened_at": door_reopened, "rset": score["rset"], "people_exposed": sum(1 for o in engine.occupants if o.fed > 0),
        "over_dose": sum(1 for o in engine.occupants if o.fed >= tenability.FED_LIMIT),
    }


async def main():
    rows = [await contain(m) for m in ("none", "autonomous", "sprinkler-only")]
    for r in rows: print(r, flush=True)
    (OUT / "containment.json").write_text(json.dumps(rows, indent=1))

asyncio.run(main())
