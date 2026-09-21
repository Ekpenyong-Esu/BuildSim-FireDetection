"""Print BuildSim's four layers, with live facts from a running BuildSim.

    cd firelab && .venv/bin/python buildsim_notes/layers.py

The code is split the way the layers are, so each piece has one job:

    Layer            a plain record: what a layer is and what was found in it
    Probe            the only thing that talks to BuildSim (HTTP GET)
    map_layer ...    one function per layer, each returns a Layer
    render           turns Layers into text
    main             runs the four probes in order and prints the result

Nothing here decides anything or writes to BuildSim; it only looks.
"""

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Runnable from anywhere: put the repository root (the parent of `firelab/`) on
# the path so the `firelab.*` imports resolve when started as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from firelab.adapters.buildsim.transport import BuildSimError, Transport
from firelab.app.config import Config

# --- the record ---------------------------------------------------------------

@dataclass
class Layer:
    """One layer of BuildSim: what it is, how firelab uses it, what is in it now."""

    number: int
    name: str
    job: str  # what the layer does, in one sentence
    firelab: str  # how firelab uses it, in one sentence
    facts: list[str] = field(default_factory=list)  # what the probe found, one line each


# The four layers, described once. The probes below only add facts to these.
LAYERS = (
    Layer(1, "The map",
          "Floor plans, doorways and stairs, built into the binary and never changed.",
          "Read once at startup and turned into firelab's rooms and door-gated couplings."),
    Layer(2, "The memory",
          "One in-memory store: equipment, layers, effects, alerts, doors, people, head counts, sessions.",
          "Everything firelab draws is a write here; each write replaces its whole collection."),
    Layer(3, "The doors and windows",
          "The REST API: one handler per resource, plus a route finder over the walkable graph.",
          "Every firelab read and write goes through here; closed fire doors are published so the route finder avoids them."),
    Layer(4, "The loudspeaker",
          "A WebSocket hub: every write to the memory is pushed to the open viewer tabs.",
          "firelab never talks to the viewer; it writes to the memory and the hub tells every tab."),
)


# --- talking to BuildSim ----------------------------------------------------------

class Probe:
    """Read-only access to BuildSim. The one place that knows HTTP exists."""

    def __init__(self, base_url: str) -> None:
        self._transport = Transport(base_url)

    async def get(self, path: str, **params):
        return await self._transport.request("GET", path, params=params or None)

    async def is_up(self) -> bool:
        try:
            await self.get("/healthz")
            return True
        except BuildSimError:
            return False

    async def close(self) -> None:
        await self._transport.aclose()


# --- one function per layer ---------------------------------------------------

async def map_layer(probe: Probe) -> Layer:
    """Layer 1: the floor plans built into the program."""
    layer = LAYERS[0]
    building = await probe.get("/api/building")
    levels = [level["id"] for level in building.get("levels", [])]
    layer.facts.append(f"building: {building.get('name')} with {len(levels)} floors: {', '.join(levels)}")
    for level in levels:
        floor = await probe.get(f"/api/building/floors/{level}")
        graph = floor.get("walkable_graph") or {}
        layer.facts.append(
            f"{level}: {len(floor.get('rooms', []))} rooms, walkable graph of "
            f"{len(graph.get('nodes', []))} nodes and {len(graph.get('edges', []))} edges"
        )
    edges = await probe.get("/api/building/cross-floor-edges") or []
    stairs = sum(1 for e in edges if e.get("type") == "stair")
    layer.facts.append(f"{len(edges)} cross-floor edges, {stairs} of them stairs (lifts are ignored for escape)")
    return layer


async def memory_layer(probe: Probe) -> Layer:
    """Layer 2: the in-memory store of everything that can change."""
    layer = LAYERS[1]
    equipment = await probe.get("/api/equipment") or []
    sensors = sum(len(item.get("sensors", [])) for item in equipment)
    layer.facts.append(f"{len(equipment)} equipment items registered, carrying {sensors} sensors")
    mine = [item for item in equipment if str(item.get("id", "")).startswith("fl-")]
    layer.facts.append(f"{len(mine)} of them are firelab's (ids starting with fl-)")
    occupancy = await probe.get("/api/occupancy") or {}
    rooms = occupancy if isinstance(occupancy, dict) else {}
    layer.facts.append(f"head counts kept for {len(rooms)} rooms right now")
    layer.facts.append("no physics and no clock live here: a value stays as written until the next write")
    return layer


async def api_layer(probe: Probe) -> Layer:
    """Layer 3: the REST handlers, including the route finder and the session API."""
    layer = LAYERS[2]
    # Ask the route finder for the way out of the office the experiments use. When
    # a fire is burning there its door is closed, and the finder then refuses to
    # route through it, which is the behaviour firelab relies on.
    try:
        route = await probe.get(
            "/api/graph/route",
            from_name="A3505", from_level="level2", to_name="A1016", to_level="level0", type="walkable",
        )
        path = (route or {}).get("path") or []
        floors = sorted({node.get("level") for node in path if node.get("level")})
        layer.facts.append(
            f"route A3505 (level2) to exit A1016 (level0): {len(path)} waypoints across {', '.join(floors)}"
        )
    except BuildSimError:
        layer.facts.append(
            "route A3505 (level2) to exit A1016 (level0): none found, because a closed fire door "
            "seals the room and the finder will not route through it"
        )
    layer.facts.append("the finder skips rooms whose door is closed, which is why firelab publishes door state")
    layer.facts.append("session endpoints hold the per-tab outlines and the drawn escape route")
    return layer


async def hub_layer(probe: Probe) -> Layer:
    """Layer 4: the WebSocket hub that pushes every change to the viewer tabs."""
    layer = LAYERS[3]
    sessions = await probe.get("/api/sessions") or []
    layer.facts.append(f"{len(sessions)} viewer tab(s) connected")
    for session in sessions:
        route = (session.get("route") or {}).get("path") or []
        layer.facts.append(
            f"tab {str(session.get('id'))[:8]}: mode {session.get('viewport', {}).get('mode')}, "
            f"{len(session.get('highlights') or [])} outlined rooms, route of {len(route)} waypoints"
        )
    layer.facts.append("a reconnecting tab is sent its stored outlines and route again")
    return layer


# --- presentation ------------------------------------------------------------

def render(layers: list[Layer], live: bool) -> str:
    """The layers as text, outer layer last, the way firelab meets them."""
    lines = ["BuildSim, from the inside out", ""]
    for layer in layers:
        lines.append(f"{layer.number}. {layer.name}")
        lines.append(f"   what it does:         {layer.job}")
        lines.append(f"   how firelab uses it:  {layer.firelab}")
        if live:
            for fact in layer.facts:
                lines.append(f"   - {fact}")
        lines.append("")
    if not live:
        lines.append("BuildSim is not running, so only the descriptions are shown. Start it with")
        lines.append("`cd buildingsim && make run` to see the live facts.")
    return "\n".join(lines)


# --- running it --------------------------------------------------------------

async def main() -> None:
    probe = Probe(Config().buildsim_url)
    try:
        live = await probe.is_up()
        if live:
            for probe_layer in (map_layer, memory_layer, api_layer, hub_layer):
                await probe_layer(probe)
        print(render(list(LAYERS), live))
    finally:
        await probe.close()


if __name__ == "__main__":
    asyncio.run(main())
