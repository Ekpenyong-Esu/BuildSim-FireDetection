"""Placing and removing what burns: sources, and the presets built from them."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domain import sensing, sources
from .. import presets as presets_mod
from . import devices

if TYPE_CHECKING:
    from .state import EngineState


def ignite(
    engine: EngineState, space: str, kind: str, growth: str, delay: float, peak_kw: float
) -> dict:
    """Schedule a fire or a nuisance. `delay` lets it start later."""
    if space not in engine.world.spaces:
        raise KeyError(space)
    if kind not in sources.KINDS:
        raise ValueError(kind)
    source = sources.Source(
        id=f"src-{len(engine.sources) + 1}-{int(engine.now)}",
        kind=kind,
        space=space,
        t_start=engine.now + max(0.0, delay),
        growth=growth,
        peak_kw=peak_kw,
    )
    engine.sources.append(source)
    engine.log("scenario", f"{kind} source scheduled in {engine.world.spaces[space].name}")
    return source.__dict__


def remove_source(engine: EngineState, source_id: str) -> None:
    """Put a source out. What it already emitted still has to disperse."""
    engine.sources = [s for s in engine.sources if s.id != source_id]


def apply_preset(engine: EngineState, preset_id: str, space: str) -> dict:
    """Instrument the room, then set up the situation described by the preset."""
    preset = presets_mod.BY_ID.get(preset_id)
    if preset is None:
        raise KeyError(preset_id)
    if space not in engine.world.spaces:
        raise KeyError(space)
    # Instrument the room and its neighbours, so cross-room agreement works.
    devices.deploy(engine, [space, *neighbours_of(engine, space)], list(sensing.MODALITIES))
    if preset.fault != "none":
        device_id = f"fl-{space.replace('/', '-')}-smoke"
        if device_id in engine.devices:
            devices.set_fault(engine, device_id, preset.fault)
    source = None
    if preset.kind:  # "drifting-sensor" has no source: nothing is burning
        source = ignite(engine, space, preset.kind, preset.growth, preset.delay, preset.peak_kw)
    engine.log("scenario", f"preset \"{preset.name}\" in {engine.world.spaces[space].name}")
    return {"preset": preset.id, "source": source}


def neighbours_of(engine: EngineState, space: str) -> list[str]:
    """Rooms joined to this one by a doorway."""
    return [
        link.b if link.a == space else link.a
        for link in engine.world.couplings
        if space in (link.a, link.b)
    ]
