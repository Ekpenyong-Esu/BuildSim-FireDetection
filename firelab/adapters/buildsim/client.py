"""One method per BuildSim URL. Every method is exactly one HTTP call.

Nothing here decides anything: no retries, no caching, no opinion about fire.
Keeping the whole catalogue flat in one file means you can find any URL the
project uses by reading down a single page.
"""

from typing import Any

from .transport import BuildSimError, Transport
from .viewer import ViewerSessions


class BuildSim:
    """A typed wrapper around BuildSim's REST API."""

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        """Point it at a running BuildSim and keep one connection pool."""
        self._transport = Transport(base_url, timeout)  # the one connection pool; every call goes through it
        self.viewer = ViewerSessions(self._transport)  # highlights and routes go to a viewer tab, not the building

    async def aclose(self) -> None:
        """Shut the connection pool down on exit."""
        await self._transport.aclose()

    # --- reading the building -------------------------------------------------

    async def health(self) -> bool:
        """Is BuildSim up? Never raises, so the UI can show it as simply down."""
        try:
            await self._transport.request("GET", "/healthz")
            return True
        except BuildSimError:
            return False

    async def building(self) -> dict:
        """The building's name and its list of levels."""
        return await self._transport.request("GET", "/api/building")

    async def floor(self, level: str) -> dict:
        """One level's rooms and its walkable graph."""
        return await self._transport.request("GET", f"/api/building/floors/{level}")

    async def route(
        self,
        from_name: str,
        to_name: str,
        from_level: str,
        to_level: str = "",
        graph: str = "walkable",
    ) -> dict | None:
        """Ask BuildSim to walk someone from one room to another.

        Sending `from_level`/`to_level` instead of a single `level` is what picks
        BuildSim's merged multi-floor graph, where the storeys are joined by real
        stairwells. Pinning one `level` confines the answer to that floor, which
        is how an upstairs occupant ends up "escaping" to a stairwell rather than
        to a door. The qualified levels also disambiguate a room name that
        appears on more than one storey.

        Returns None when there is no path, which is normal rather than an error.
        """
        try:
            return await self._transport.request(
                "GET",
                "/api/graph/route",
                params={
                    "from_name": from_name,
                    "from_level": from_level,
                    "to_name": to_name,
                    "to_level": to_level or from_level,
                    "type": graph,
                },
            )
        except BuildSimError:
            return None

    async def cross_floor_edges(self) -> list[dict]:
        """The stairs and lifts that join the storeys.

        BuildSim uses these to merge the per-floor walkable graphs; we use them
        as couplings, so smoke can climb a stairwell the way it really does.
        """
        return await self._transport.request("GET", "/api/building/cross-floor-edges") or []

    # --- writing state --------------------------------------------------------
    # Each of these replaces the whole collection, so anything left out
    # disappears from the viewer. That is why the publisher always sends
    # a complete list.

    async def put_room_layers(self, layers: list[dict]) -> None:
        """Colour the room floors."""
        await self._transport.request("PUT", "/api/room-layers", json=layers)

    async def put_effects(self, effects: list[dict]) -> None:
        """Smoke and fire particle effects."""
        await self._transport.request("PUT", "/api/effects", json=effects)

    async def put_alerts(self, alerts: list[dict]) -> None:
        """Floating alert markers."""
        await self._transport.request("PUT", "/api/alerts", json=alerts)

    async def put_doors(self, doors: list[dict]) -> None:
        """Open or closed door state."""
        await self._transport.request("PUT", "/api/doors", json=doors)

    async def put_entities(self, entities: list[dict]) -> None:
        """The moving occupant markers."""
        await self._transport.request("PUT", "/api/entities", json=entities)

    async def put_occupancy(self, occupancy: dict) -> None:
        """Head count per room."""
        await self._transport.request("PUT", "/api/occupancy", json=occupancy)

    # --- equipment, sensors, actuators ---------------------------------------

    async def create_equipment_bulk(self, items: list[dict]) -> Any:
        """Install many sensors and actuators in one call, rather than 3000."""
        return await self._transport.request("POST", "/api/equipment/bulk", json=items)

    async def delete_equipment(self, equipment_id: str) -> None:
        """Remove one piece of installed equipment."""
        await self._transport.request("DELETE", f"/api/equipment/{equipment_id}")

    async def set_sensor_value(self, sensor_id: str, value: str) -> None:
        """Push a reading so it shows on the sensor's label in the viewer."""
        await self._transport.request(
            "PUT", f"/api/sensors/{sensor_id}/value", json={"data_type": "text", "value": value}
        )

    async def set_actuator_state(self, actuator_id: str, state: str) -> None:
        """Switch a sprinkler or door actuator on or off."""
        await self._transport.request(
            "PUT", f"/api/actuators/{actuator_id}/state", json={"state": state}
        )
