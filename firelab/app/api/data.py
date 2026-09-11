"""Getting the recorded run back out: one room's chart, or the whole CSV."""

import csv
import io

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from ...domain.history import COLUMNS
from .. import snapshot as snapshot_mod
from ..runtime import engine

router = APIRouter()


@router.get("/api/history")
async def history(space: str) -> dict:
    """One room's recorded time series, plus why P(fire) is where it is."""
    return {
        "space": space,
        "columns": list(COLUMNS),
        "points": engine.history.series(space),
        "why": snapshot_mod.why(engine, space),
    }


@router.get("/api/export.csv", response_class=PlainTextResponse)
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
