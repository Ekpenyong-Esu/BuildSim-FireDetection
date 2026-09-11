"""Supervision: who is allowed to act, and manual overrides."""

from fastapi import APIRouter

from ..engine import actuation
from ..runtime import engine
from .models import CommandBody, ModeBody

router = APIRouter()


@router.post("/api/agent/mode")
async def mode(body: ModeBody) -> dict:
    """Switch between the agent acting by itself and needing a human."""
    engine.config.response.auto = body.auto
    engine.log("info", "autonomous response " + ("enabled" if body.auto else "disabled"))
    return {"auto": body.auto}


@router.post("/api/actuators/command")
async def command(body: CommandBody) -> dict:
    """A human-issued command. It still has to pass the same interlocks."""
    return actuation.override(engine, body.kind, body.space, body.value)
