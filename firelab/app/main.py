"""HTTP surface: REST for commands, SSE for live state, static files for the UI."""

import asyncio
import contextlib
import csv
import io
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..domain.history import COLUMNS
from ..domain.occupants import ROLE_BY_KEY, ROLES
from . import presets as presets_mod
from . import snapshot as snapshot_mod
from .config import Config
from .engine import Engine

UI_DIST = Path(__file__).resolve().parent.parent / "ui" / "dist"  # the built Svelte app

# The viewer stops drawing individual markers long before this; it is here so an
# untrusted request cannot ask for a million people.
MAX_OCCUPANTS = 2000

# One engine for the whole process. There is one building, so one simulation.
engine = Engine(Config())


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the simulation loop when the server boots, stop it when it exits."""
    await engine.start()
    yield
    await engine.stop()


app = FastAPI(title="firelab", version="0.1.0", lifespan=lifespan)


# The request bodies. Pydantic checks the types, so a bad request is rejected
# before it ever reaches the engine.
class ClockBody(BaseModel):
    seconds: float | None = None
    factor: float | None = None
    running: bool | None = None


class IgniteBody(BaseModel):
    space: str
    kind: str = "flaming"
    growth: str = "medium"
    delay: float = 0.0
    peak_kw: float = Field(default=2000.0, gt=0)  # gt=0: a fire with no heat is nonsense


class DeployBody(BaseModel):
    spaces: list[str]
    modalities: list[str] = ["smoke", "co", "temperature"]


class FaultBody(BaseModel):
    device_id: str
    fault: str


class CommandBody(BaseModel):
    kind: str
    space: str
    value: str


class ModeBody(BaseModel):
    auto: bool


class PresetBody(BaseModel):
    preset: str
    space: str


class PopulationBody(BaseModel):
    # A whole mix, so a partial one cannot silently empty the building.
    population: dict[str, int]


@app.get("/healthz")
async def healthz() -> dict:
    """Are we up, and can we still see BuildSim?"""
    return {"ok": True, "buildsim": engine.connected}


@app.get("/api/state")
async def state() -> dict:
    """The current snapshot, for anything that cannot use the event stream."""
    return engine.snapshot()


@app.get("/api/rooms")
async def rooms() -> list[dict]:
    """All 956 rooms, for the room picker."""
    return engine.rooms()


@app.get("/api/config")
async def get_config() -> dict:
    """Read the current settings."""
    return engine.config.to_dict()


@app.put("/api/config")
async def put_config(patch: dict) -> dict:
    """Change some settings. Send only the fields you want to change."""
    engine.config.apply(patch)
    if "seed" in patch:
        engine.reseed()  # a run is only repeatable if the randomness restarts too
    return engine.config.to_dict()


@app.get("/api/events")
async def events() -> StreamingResponse:
    """Server-sent events: the browser holds this open and receives every tick.

    Push beats polling here because the snapshot changes on the engine's clock,
    not the browser's.
    """
    queue = engine.subscribe()

    async def stream():
        try:
            yield f"data: {json.dumps(engine.snapshot())}\n\n"  # current state first
            while True:
                try:
                    snapshot = await asyncio.wait_for(queue.get(), timeout=5.0)
                    yield f"data: {json.dumps(snapshot)}\n\n"
                except asyncio.TimeoutError:
                    # Nothing happened for 5 s. Send anyway, to keep the
                    # connection from being closed by a proxy.
                    yield f"data: {json.dumps(engine.snapshot())}\n\n"
        finally:
            engine.unsubscribe(queue)  # always tidy up, even on disconnect

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/clock")
async def clock(body: ClockBody) -> dict:
    """Play, pause, jump in time, or change how fast time runs."""
    engine.set_clock(body.seconds, body.factor)
    if body.running is not None:
        engine.set_running(body.running)
    return engine.snapshot()["clock"]


@app.post("/api/reset")
async def reset() -> dict:
    """Clear the fires, the alarms and the scorecard; keep the building."""
    engine.reset()
    return {"ok": True}


@app.post("/api/reload")
async def reload() -> dict:
    """Re-read the floor plans from BuildSim."""
    await engine.load()
    return engine.snapshot()["buildsim"]


@app.post("/api/scenario/ignite")
async def ignite(body: IgniteBody) -> dict:
    """Start a fire or a nuisance in one room."""
    try:
        return engine.ignite(body.space, body.kind, body.growth, body.delay, body.peak_kw)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/scenario/{source_id}")
async def extinguish(source_id: str) -> dict:
    """Put a source out. The heat and smoke it made still have to disperse."""
    engine.remove_source(source_id)
    return {"ok": True}


@app.get("/api/presets")
async def list_presets() -> list[dict]:
    """The six one-click scenarios."""
    return presets_mod.catalogue()


@app.get("/api/roles")
async def list_roles() -> list[dict]:
    """The kinds of people who can be in the building."""
    return [
        {"key": r.key, "label": r.label, "speed": r.speed, "note": r.note} for r in ROLES
    ]


@app.put("/api/population")
async def put_population(body: PopulationBody) -> dict:
    """Set how many of each role there are and scatter them again."""
    unknown = set(body.population) - set(ROLE_BY_KEY)
    if unknown:
        raise HTTPException(status_code=400, detail=f"unknown roles: {', '.join(sorted(unknown))}")
    if any(count < 0 for count in body.population.values()):
        raise HTTPException(status_code=400, detail="counts cannot be negative")
    total = sum(body.population.values())
    if total > MAX_OCCUPANTS:
        raise HTTPException(status_code=400, detail=f"at most {MAX_OCCUPANTS} people")
    engine.config.population = {key: int(v) for key, v in body.population.items()}
    engine.place_occupants(engine.config.population)
    engine.log("info", f"population set to {total} people")
    return engine.config.to_dict()


@app.post("/api/scenario/preset")
async def apply_preset(body: PresetBody) -> dict:
    """Run a preset in a room: ignite it, and inject its fault if it has one."""
    try:
        result = engine.apply_preset(body.preset, body.space)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await engine.register_equipment()
    return result


@app.get("/api/history")
async def history(space: str) -> dict:
    """One room's recorded time series, plus why P(fire) is where it is."""
    return {
        "space": space,
        "columns": list(COLUMNS),
        "points": engine.history.series(space),
        "why": snapshot_mod.why(engine, space),
    }


@app.get("/api/export.csv", response_class=PlainTextResponse)
async def export_csv() -> PlainTextResponse:
    """Every recorded sample, for the report or for training a model offline."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["space", "level", "room", "label", *COLUMNS])
    # The label is the ground truth: which kind of source, if any, was in the
    # room. That is what a supervised model would be trained to predict.
    labels = {source.space: source.kind for source in engine.sources}
    for key, points in engine.history.tracks.items():
        space = engine.world.spaces.get(key)
        level = space.level if space else ""
        name = space.name if space else key
        label = labels.get(key, "none")
        for point in points:
            writer.writerow([key, level, name, label, *point])
    return PlainTextResponse(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="firelab-run.csv"'},
    )


@app.post("/api/sensors/deploy")
async def deploy(body: DeployBody) -> dict:
    """Install sensors in some rooms and mirror them into BuildSim."""
    count = engine.deploy(body.spaces, body.modalities)
    registered = await engine.register_equipment()
    return {"deployed": count, "registered": registered}


@app.post("/api/sensors/undeploy")
async def undeploy(body: DeployBody) -> dict:
    """Take the sensors out again, leaving those rooms unmonitored."""
    return {"removed": engine.undeploy(body.spaces)}


@app.post("/api/sensors/fault")
async def fault(body: FaultBody) -> dict:
    """Break one sensor on purpose: dead, dropout, stuck or drifting."""
    try:
        engine.set_fault(body.device_id, body.fault)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@app.post("/api/agent/mode")
async def mode(body: ModeBody) -> dict:
    """Switch between the agent acting by itself and needing a human."""
    engine.config.response.auto = body.auto
    engine.log("info", "autonomous response " + ("enabled" if body.auto else "disabled"))
    return {"auto": body.auto}


@app.post("/api/actuators/command")
async def command(body: CommandBody) -> dict:
    """A human-issued command. It still has to pass the same interlocks."""
    return engine.command(body.kind, body.space, body.value)


# Serve the built UI, if it has been built. Without this the API still works.
if UI_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=UI_DIST / "assets"), name="assets")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(UI_DIST / "index.html")
