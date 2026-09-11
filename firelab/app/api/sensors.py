"""Installing sensors and breaking them on purpose."""

from fastapi import APIRouter, HTTPException

from ..engine import devices
from ..runtime import engine
from .models import DeployBody, FaultBody

router = APIRouter()


@router.post("/api/sensors/deploy")
async def deploy(body: DeployBody) -> dict:
    """Install sensors in some rooms and mirror them into BuildSim."""
    count = devices.deploy(engine, body.spaces, body.modalities)
    registered = await devices.register(engine)
    return {"deployed": count, "registered": registered}


@router.post("/api/sensors/undeploy")
async def undeploy(body: DeployBody) -> dict:
    """Take the sensors out again, leaving those rooms unmonitored."""
    return {"removed": devices.undeploy(engine, body.spaces)}


@router.post("/api/sensors/fault")
async def fault(body: FaultBody) -> dict:
    """Break one sensor on purpose: dead, dropout, stuck or drifting."""
    try:
        devices.set_fault(engine, body.device_id, body.fault)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}
