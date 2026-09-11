"""Assemble the application: routers for the API, static files for the built UI.

Everything you can actually ask the server to do lives in `api/`; this file only
wires it together and ties the engine's lifetime to the server's.
"""

import contextlib
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import ROUTERS
from .runtime import engine

UI_DIST = Path(__file__).resolve().parent.parent / "ui" / "dist"  # the built Svelte app


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the simulation loop when the server boots, stop it when it exits."""
    await engine.start()
    yield
    await engine.stop()


app = FastAPI(title="firelab", version="0.1.0", lifespan=lifespan)

for router in ROUTERS:
    app.include_router(router)


# Serve the built UI, if it has been built. Without this the API still works.
if UI_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=UI_DIST / "assets"), name="assets")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(UI_DIST / "index.html")
