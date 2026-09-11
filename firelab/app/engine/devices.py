"""Installing, removing and breaking sensors.

Deployment is what makes a room monitored at all: a room with no device here
has no readings, no features and no agent, and so is invisible to the system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...adapters import publisher
from ...adapters.buildsim import BuildSimError
from ...domain import agent as agent_mod
from ...domain import sensing
from ...domain.features import Window

if TYPE_CHECKING:
    from .state import EngineState


def deploy(engine: EngineState, spaces: list[str], modalities: list[str]) -> int:
    """Install sensors. Deploying is what makes a room monitored at all."""
    count = 0
    for key in spaces:
        if key not in engine.world.spaces:
            continue
        for modality in modalities:
            if modality not in sensing.MODALITIES:
                continue
            device_id = f"fl-{key.replace('/', '-')}-{modality}"
            if device_id in engine.devices:
                continue  # already installed
            device = sensing.Device.create(device_id, key, modality)
            device.interval = engine.config.sensors.interval
            device.noise *= engine.config.sensors.noise_scale
            device.next_sample = engine.now
            engine.devices[device_id] = device
            # A monitored room also needs somewhere to keep readings and an
            # agent to hold its state.
            engine.windows.setdefault(key, Window(space=key))
            engine.agents.setdefault(key, agent_mod.RoomAgent(space=key, since=engine.now))
            count += 1
    engine.log("info", f"deployed {count} devices")
    engine.mark_dirty()
    return count


def undeploy(engine: EngineState, spaces: list[str]) -> int:
    """Remove the sensors and everything derived from them."""
    targets = {d.id for d in engine.devices.values() if d.space in spaces}
    for device_id in targets:
        del engine.devices[device_id]
    for key in spaces:
        engine.windows.pop(key, None)
        engine.agents.pop(key, None)
        engine.probabilities.pop(key, None)
        engine.features.pop(key, None)
    return len(targets)


def set_fault(engine: EngineState, device_id: str, fault: str) -> None:
    """Break one sensor on purpose, to see whether the rest cope."""
    device = engine.devices.get(device_id)
    if device is None or fault not in sensing.FAULTS:
        raise KeyError(device_id)
    device.fault = fault
    device.drift = 0.0  # start the drift from wherever it is now
    engine.log("fault", f"{device_id} -> {fault}")


async def register(engine: EngineState) -> int:
    """Mirror every installed device into BuildSim's equipment tree."""
    if not engine.connected:
        return 0
    items = publisher.equipment(engine.world, engine.devices.values())
    if not items:
        return 0
    try:
        result = await engine.client.create_equipment_bulk(items)
    except BuildSimError as exc:
        engine.log("error", f"equipment registration failed: {exc}")
        return 0
    created = (result or {}).get("created", 0)
    engine.log("info", f"registered {created} equipment items in BuildSim")
    return created
