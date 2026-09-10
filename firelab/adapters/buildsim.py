"""HTTP adapter for BuildSim. The only module that knows BuildSim exists."""

from typing import Any

import httpx

# BuildSim floor plans are drawn in units of 0.5 m.
UNITS_TO_METRES = 0.5


class BuildSimError(RuntimeError):
    """Anything that went wrong talking to BuildSim, network or HTTP status."""


class BuildSim:
    """A typed wrapper around BuildSim's REST API.

    Every method is one HTTP call. Keeping them all here means the rest of the
    project never has to know a URL.
    """

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)
        self._session_id: str | None = None  # cached viewer tab
        self._session_checked = -1e9  # long ago, so the first lookup always runs

    async def aclose(self) -> None:
        """Shut the connection pool down on exit."""
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        """Make one call and turn every kind of failure into `BuildSimError`."""
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise BuildSimError(f"{method} {path}: {exc}") from exc
        if response.status_code >= 400:
            raise BuildSimError(f"{method} {path}: {response.status_code} {response.text[:200]}")
        if not response.content:
            return None  # a successful PUT usually replies with nothing
        return response.json()

    # --- reading the building -------------------------------------------------

    async def health(self) -> bool:
        """Is BuildSim up? Never raises, so the UI can show it as simply down."""
        try:
            await self._request("GET", "/healthz")
            return True
        except BuildSimError:
            return False

    async def building(self) -> dict:
        """The building's name and its list of levels."""
        return await self._request("GET", "/api/building")

    async def floor(self, level: str) -> dict:
        """One level's rooms and its walkable graph."""
        return await self._request("GET", f"/api/building/floors/{level}")

    async def route(
        self, from_name: str, to_name: str, level: str, graph: str = "walkable"
    ) -> dict | None:
        """Ask BuildSim to walk someone from one room to another.

        Returns None when there is no path, which is normal rather than an error.
        """
        try:
            return await self._request(
                "GET",
                "/api/graph/route",
                params={
                    "from_name": from_name,
                    "to_name": to_name,
                    "level": level,
                    "type": graph,
                },
            )
        except BuildSimError:
            return None

    # --- writing state --------------------------------------------------------
    # Each of these replaces the whole collection, so anything left out
    # disappears from the viewer. That is why the publisher always sends
    # a complete list.

    async def put_room_layers(self, layers: list[dict]) -> None:
        """Colour the room floors."""
        await self._request("PUT", "/api/room-layers", json=layers)

    async def put_effects(self, effects: list[dict]) -> None:
        """Smoke and fire particle effects."""
        await self._request("PUT", "/api/effects", json=effects)

    async def put_alerts(self, alerts: list[dict]) -> None:
        """Floating alert markers."""
        await self._request("PUT", "/api/alerts", json=alerts)

    async def put_doors(self, doors: list[dict]) -> None:
        """Open or closed door state."""
        await self._request("PUT", "/api/doors", json=doors)

    async def put_entities(self, entities: list[dict]) -> None:
        """The moving occupant markers."""
        await self._request("PUT", "/api/entities", json=entities)

    async def put_occupancy(self, occupancy: dict) -> None:
        """Head count per room."""
        await self._request("PUT", "/api/occupancy", json=occupancy)

    # --- equipment, sensors, actuators ---------------------------------------

    async def create_equipment_bulk(self, items: list[dict]) -> Any:
        """Install many sensors and actuators in one call, rather than 3000."""
        return await self._request("POST", "/api/equipment/bulk", json=items)

    async def delete_equipment(self, equipment_id: str) -> None:
        """Remove one piece of installed equipment."""
        await self._request("DELETE", f"/api/equipment/{equipment_id}")

    async def set_sensor_value(self, sensor_id: str, value: str) -> None:
        """Push a reading so it shows on the sensor's label in the viewer."""
        await self._request(
            "PUT", f"/api/sensors/{sensor_id}/value", json={"data_type": "text", "value": value}
        )

    async def set_actuator_state(self, actuator_id: str, state: str) -> None:
        """Switch a sprinkler or door actuator on or off."""
        await self._request("PUT", f"/api/actuators/{actuator_id}/state", json={"state": state})

    # --- viewer sessions ------------------------------------------------------
    # A session is one open browser tab of the 3D viewer. Highlights and routes
    # are drawn per tab, not globally.

    async def sessions(self) -> list[dict]:
        """Every viewer tab BuildSim currently knows about."""
        return await self._request("GET", "/api/sessions") or []

    async def newest_session_id(self) -> str | None:
        """The most recently active tab: the one the user is probably looking at."""
        sessions = await self.sessions()
        if not sessions:
            self._session_id = None
            return None
        sessions.sort(key=lambda s: s.get("last_ws_active") or "")
        self._session_id = sessions[-1].get("id")
        return self._session_id

    async def viewer_session_id(self, now: float, refresh: float = 30.0) -> str | None:
        """Cached session lookup; the viewer rarely changes tab."""
        if self._session_id is None or now - self._session_checked >= refresh:
            self._session_checked = now
            return await self.newest_session_id()
        return self._session_id

    async def put_session_highlights(self, session_id: str, highlights: list[dict]) -> None:
        """Outline rooms in colour in one viewer tab."""
        await self._request("PUT", f"/api/sessions/{session_id}/highlights", json=highlights)

    async def put_session_route(self, session_id: str, route: dict) -> None:
        """Draw an escape route line in one viewer tab."""
        await self._request("PUT", f"/api/sessions/{session_id}/route", json=route)
