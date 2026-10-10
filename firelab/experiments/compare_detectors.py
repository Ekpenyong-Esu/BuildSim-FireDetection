"""Score the same scenarios with the language-model detector, paced to the wall clock.

    cd firelab && .venv/bin/python experiments/compare_detectors.py

Needs BuildSim on :9090 and LLM_BASE_URL, LLM_API_KEY and LLM_MODEL (or firelab/.env).
Writes results/results_llm.json in the same shape as results.json, plus a
`llm` block per run with what the model cost and how much of the scoring it did.

The rule's harness runs a 20-minute scenario in a few real seconds because
nothing waits for anything. The model does wait: an answer takes about eight
real seconds and is only good for a minute of simulated time, so this script
sleeps between ticks exactly as the live engine paces itself, at the speed the
detector has shown it can keep up with. One scenario therefore takes about the
same real time as it would on the dashboard, six to seven minutes at 3x.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from firelab.app import dotenv
from firelab.app.config import Config
from firelab.app.engine import building, devices, scenario, session
from firelab.app.engine.core import Engine
from firelab.experiments.run_experiments import MINUTES, OUT, ROOM, STEP, peak, since

dotenv.load()
START_FACTOR = 3.0  # times real time offered every tick; the detector's measured pace caps it
RUNS = (
    # (preset, noise, fault): the six presets, the two nuisance runs where the rule's
    # margin was thinnest, and the fault that cost the rule the most time.
    ("office-fire", 1.0, None),
    ("overnight-smoulder", 1.0, None),
    ("kitchen-cooking", 1.0, None),
    ("dust-storm", 1.0, None),
    ("blind-spot", 1.0, None),
    ("drifting-sensor", 1.0, None),
    ("kitchen-cooking", 2.0, None),
    ("kitchen-cooking", 3.0, None),
    ("office-fire", 1.0, "stuck"),
)


async def fresh(noise: float) -> Engine:
    config = Config()
    config.step_seconds = STEP
    config.sensors.noise_scale = noise
    config.detector.kind = "llm"
    config.factor = START_FACTOR
    engine = Engine(config)
    if engine.detector.name != "llm":
        raise SystemExit("the LLM detector is not configured: " + engine.journal[-1]["message"])
    await building.load(engine)
    await engine._start_detector()
    engine.connected = False  # measure, do not draw
    return engine


async def run_paced(engine: Engine, seconds: float, t0: float) -> list:
    """Tick the engine at the detector's pace and note, every 5 s, who scored the fire room."""
    trace = []
    factors = []
    for _ in range(int(seconds / STEP)):
        tick_started = time.monotonic()
        # The live dial stays wherever the cap pushed it until a person raises it. Nobody
        # is here to do that, so the harness offers the start speed again every tick and
        # lets the cap decide: a stall on the shared endpoint slows the run, and the run
        # speeds back up once answers arrive on time again.
        engine.config.factor = START_FACTOR
        engine._pace_for_detector()
        factors.append(engine.config.factor)
        await engine._tick(STEP)
        t = engine.now - t0
        if int(t) % 5 == 0:
            trace.append([round(t), round(engine.probabilities.get(ROOM, 0.0), 3),
                          "model" if engine.detector.in_charge(ROOM) else "rule"])
        # Sleep off whatever real time this simulated second is owed at the current speed.
        # The debt is per second, not from the start of the run, so a slow stretch does
        # not make the run race ahead afterwards.
        owed = STEP / engine.config.factor - (time.monotonic() - tick_started)
        if owed > 0:
            await asyncio.sleep(owed)
        else:
            await asyncio.sleep(0)  # let the worker run even when we are behind
    return trace, factors


async def scenario_run(preset: str, noise: float, fault: str | None) -> dict:
    engine = await fresh(noise)
    session.reset(engine)
    t0 = engine.now
    scenario.apply_preset(engine, preset, ROOM)
    if fault:
        devices.set_fault(engine, f"fl-{ROOM.replace('/', '-')}-smoke", fault)
    wall = time.monotonic()
    trace, factors = await run_paced(engine, MINUTES * 60, t0)
    wall = time.monotonic() - wall
    await engine._stop_detector()
    score = engine.score.summary()
    space = engine.world.spaces[ROOM]
    j = engine.journal
    name = space.name
    rows = engine.history.tracks.get(ROOM, [])
    active = [row for row in trace if row[1] >= 0.05 or row[2] == "model"]
    verdicts = [
        [round(l["t"] - t0), l["message"]]
        for l in j if l["kind"] == "detector" and l["message"].startswith(f"{ROOM}: model says")
    ]
    failures = [[round(l["t"] - t0), l["message"]] for l in j if "model unavailable" in l["message"]]
    return {
        "preset": preset, "noise": noise, "auto": True, "fault": fault,
        "detections": score["detections"], "misses": score["misses"],
        "false_alarms": score["false_alarms"], "alarm_delay": score["alarm_delay"],
        "rset": score["rset"], "rset_from_alarm": score["rset_from_alarm"],
        "investigating_at": since(j, f"{name}: NORMAL -> INVESTIGATING", t0),
        "confirmed_at": since(j, "-> CONFIRMED", t0),  # the first room to confirm, as the rule's harness counts it
        "room_confirmed_at": since(j, f"{name}: PRE_ALARM -> CONFIRMED", t0),  # the fire room itself
        # Every state change of the fire room, so flip-flopping shows up as more lines.
        "room_states": [f"{l['t']-t0:.0f}s {l['message'].split(': ', 1)[1]}" for l in j if l["kind"] == "agent" and l["message"].startswith(f"{name}: ")],
        "final_state": engine.agents[ROOM].state,
        "peak_truth_temp": peak(rows, 1, 20.0, 1),
        "peak_truth_smoke": peak(rows, 2, 0.0, 3),
        "max_p_fire": peak(rows, 7, 0.0, 3),
        "sprinkler": space.sprinkler,
        "blocked": [f"{k[0]} {k[2]}: {v}" for k, v in engine.blocks.items()],
        "journal": [f"{l['t']-t0:.0f}s {l['kind']} {l['message']}" for l in j if l["kind"] in ("agent", "actuator", "interlock")][:14],
        "series": [[round(r[0]-t0, 0)] + [None if v is None else round(v, 3) for v in r[1:]] for r in rows],
        "llm": {
            "model": os.environ.get("LLM_MODEL"),
            **engine.detector.stats(),
            "speed": round(sum(factors) / len(factors), 2),  # mean of the capped dial over the run
            "speed_min": min(factors),
            "wall_seconds": round(wall),
            # Share of the fire room's 5 s samples, once something was happening, that the model scored.
            "model_share": round(sum(1 for row in active if row[2] == "model") / max(len(active), 1), 2),
            "max_p_model": max((row[1] for row in trace if row[2] == "model"), default=None),
            "trace": trace,
            "verdicts": verdicts,
            "failures": failures,
        },
    }


async def main() -> None:
    OUT.mkdir(exist_ok=True)
    path = OUT / "results_llm.json"
    results = json.loads(path.read_text()) if path.exists() else {"presets": [], "noise": [], "faults": []}
    done = {(r["preset"], r["noise"], r["fault"]) for section in results.values() for r in section}
    for preset, noise, fault in RUNS:
        if (preset, noise, fault) in done:
            continue  # resumable: a crash or a Ctrl-C keeps what was measured
        r = await scenario_run(preset, noise, fault)
        section = "faults" if fault else ("noise" if noise != 1.0 else "presets")
        results[section].append(r)
        path.write_text(json.dumps(results, indent=1))
        brief = {k: r[k] for k in ("investigating_at", "confirmed_at", "room_confirmed_at", "false_alarms", "max_p_fire", "final_state")}
        brief.update({k: r["llm"][k] for k in ("asked", "answered", "failed", "latency_median_s", "speed", "speed_min", "model_share", "max_p_model")})
        print(preset, noise, fault, brief, flush=True)
    print("written", path)


if __name__ == "__main__":
    asyncio.run(main())
