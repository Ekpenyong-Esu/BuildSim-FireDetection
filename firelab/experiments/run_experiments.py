"""Headless experiments for the architecture document.

Drives the real engine tick by tick against a live BuildSim (for the floor plans
only; nothing is published back) and writes the measurements the report quotes.

    cd firelab && .venv/bin/python experiments/run_experiments.py

or, from the repository root, `firelab/.venv/bin/python -m firelab.experiments.run_experiments`.
BuildSim must be running on :9090; the experiments take several minutes.

Every run starts from a reset with the same seed, so the numbers are repeatable.
"""

import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path

# Runnable from anywhere: put the repository root (the parent of `firelab/`) on
# the path so `firelab.*` imports resolve even when started as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from firelab.app import dotenv
from firelab.app.config import Config
from firelab.app.engine import building, devices, scenario, session
from firelab.app.engine.core import Engine
from firelab.domain import sensing

ROOM = "level2/A3505"          # the office every scenario is run in
OUT = Path(__file__).resolve().parent / "results"
STEP = 1.0                     # simulated seconds per physics step
MINUTES = 20                   # how long each scenario runs


# Which detector scores the rooms: "fusion-rule" (default) or "llm". The LLM one
# also needs LLM_BASE_URL, LLM_API_KEY and LLM_MODEL, and its answers are not
# repeatable from the seed, so the report says which detector each number is from.
dotenv.load()  # firelab/.env, for the LLM detector's endpoint settings
DETECTOR = os.environ.get("FIRELAB_DETECTOR", "fusion-rule")


async def fresh(noise: float = 1.0, auto: bool = True) -> Engine:
    config = Config()
    config.step_seconds = STEP
    config.sensors.noise_scale = noise
    config.response.auto = auto
    config.detector.kind = DETECTOR
    engine = Engine(config)
    await building.load(engine)
    await engine._start_detector()   # the LLM detector's background worker, a no-op for the rule
    engine.connected = False   # measure, do not draw
    return engine


async def run(engine: Engine, seconds: float) -> None:
    for _ in range(int(seconds / STEP)):
        await engine._tick(STEP)


def first(journal, needle):
    """Simulated time of the first journal line containing `needle`, or None."""
    for line in journal:
        if needle in line["message"]:
            return line["t"]
    return None


def peak(rows: list[list[float | None]], index: int, floor: float, digits: int) -> float:
    """The largest value in one column of a room's history, ignoring gaps.

    `floor` is returned when there are no samples at all, so a room that never
    recorded anything reports its ambient value rather than crashing.
    """
    # Bind the cell to a name so the type checker can see that None is filtered out;
    # indexing the row twice does not narrow the type.
    values: list[float] = [value for row in rows if (value := row[index]) is not None]
    best: float = max(values, default=floor)
    return round(best, digits)


def since(journal, needle, t0):
    """Seconds after ignition at which `needle` was first journalled, or None."""
    at = first(journal, needle)
    return None if at is None else at - t0


async def scenario_run(preset: str, noise: float = 1.0, auto: bool = True, fault: str | None = None):
    engine = await fresh(noise, auto)
    session.reset(engine)
    t0 = engine.now
    scenario.apply_preset(engine, preset, ROOM)
    if fault:
        devices.set_fault(engine, f"fl-{ROOM.replace('/', '-')}-smoke", fault)
    await run(engine, MINUTES * 60)
    score = engine.score.summary()
    space = engine.world.spaces[ROOM]
    j = engine.journal
    name = space.name
    rows = engine.history.tracks.get(ROOM, [])
    return {
        "preset": preset, "noise": noise, "auto": auto, "fault": fault,
        "detections": score["detections"], "misses": score["misses"],
        "false_alarms": score["false_alarms"], "alarm_delay": score["alarm_delay"],
        "rset": score["rset"], "rset_from_alarm": score["rset_from_alarm"],
        "investigating_at": since(j, f"{name}: NORMAL -> INVESTIGATING", t0),
        "confirmed_at": since(j, "-> CONFIRMED", t0),
        "final_state": engine.agents[ROOM].state,
        "peak_truth_temp": peak(rows, 1, 20.0, 1),
        "peak_truth_smoke": peak(rows, 2, 0.0, 3),
        "max_p_fire": peak(rows, 7, 0.0, 3),
        "sprinkler": space.sprinkler,
        "blocked": [f"{k[0]} {k[2]}: {v}" for k, v in engine.blocks.items()],
        "journal": [f"{l['t']-t0:.0f}s {l['kind']} {l['message']}" for l in j if l["kind"] in ("agent", "actuator", "interlock")][:14],
        "series": [[round(r[0]-t0, 0)] + [None if v is None else round(v, 3) for v in r[1:]] for r in engine.history.tracks.get(ROOM, [])],
    }


async def scaling():
    rows = []
    for n in (10, 50, 100, 200, 400, 700, 956):
        engine = await fresh()
        session.reset(engine)
        keys = sorted(engine.world.spaces)[:n]
        devices.deploy(engine, keys, list(sensing.MODALITIES))
        scenario.apply_preset(engine, "office-fire", ROOM)
        await run(engine, 120)   # let the fire get going
        for factor in (1.0, 40.0):
            times = []
            for _ in range(10):
                t = time.perf_counter()
                await engine._tick(factor)   # one real tick covers `factor` simulated seconds
                times.append(time.perf_counter() - t)
            rows.append({"rooms": n, "devices": len(engine.devices), "factor": factor,
                         "median_ms": round(statistics.median(times) * 1000, 1),
                         "max_ms": round(max(times) * 1000, 1)})
            print("scaling", rows[-1], flush=True)
    return rows


async def main():
    OUT.mkdir(exist_ok=True)
    results = {}
    # 1. every preset, default noise, autonomous
    results["presets"] = []
    for p in ("office-fire", "overnight-smoulder", "kitchen-cooking", "dust-storm", "blind-spot", "drifting-sensor"):
        r = await scenario_run(p)
        print(p, {k: r[k] for k in ("detections", "false_alarms", "alarm_delay", "rset", "final_state", "peak_truth_temp", "sprinkler")}, flush=True)
        results["presets"].append(r)
    # 2. closed loop: the same fire with the agent's commands dropped (supervised mode)
    results["open_loop"] = await scenario_run("office-fire", auto=False)
    print("open loop", {k: results["open_loop"][k] for k in ("peak_truth_temp", "peak_truth_smoke", "sprinkler", "rset")}, flush=True)
    # 3. noise sweep, fire and nuisance
    results["noise"] = []
    for noise in (0.0, 1.0, 2.0, 3.0):
        for p in ("office-fire", "kitchen-cooking"):
            r = await scenario_run(p, noise=noise)
            results["noise"].append({k: r[k] for k in ("preset", "noise", "detections", "false_alarms", "alarm_delay", "max_p_fire")})
            print("noise", results["noise"][-1], flush=True)
    # 4. faults on the smoke detector during a real fire
    results["faults"] = []
    for fault in ("none", "stuck", "dropout", "drift", "dead"):
        r = await scenario_run("office-fire", fault=fault)
        results["faults"].append({k: r[k] for k in ("fault", "detections", "false_alarms", "alarm_delay", "max_p_fire")})
        print("fault", results["faults"][-1], flush=True)
    # 5. scaling
    results["scaling"] = await scaling()
    (OUT / "results.json").write_text(json.dumps(results, indent=1))
    print("written", OUT / "results.json")


if __name__ == "__main__":
    asyncio.run(main())
