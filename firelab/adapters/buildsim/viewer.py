"""Everything scoped to one open 3D viewer tab.

Highlights and escape routes are drawn per tab rather than globally, so
something has to remember which tab the user is looking at. That cache is the
only state the BuildSim adapter holds.
"""

from .transport import Transport


class ViewerSessions:
    """Tracks the active viewer tab and draws into it."""

    def __init__(self, transport: Transport) -> None:
        """Borrow the shared transport; the viewer has no connection of its own."""
        self._transport = transport  # shared with the client
        self._session_id: str | None = None  # the tab being drawn into; None until one is found
        self._checked = -1e9  # long ago, so the first lookup always runs

    async def all(self) -> list[dict]:
        """Every viewer tab BuildSim currently knows about."""
        return await self._transport.request("GET", "/api/sessions") or []

    async def newest_id(self) -> str | None:
        """The most recently active tab: the one the user is probably looking at."""
        sessions = await self.all()
        if not sessions:
            self._session_id = None
            return None
        sessions.sort(key=lambda s: s.get("last_ws_active") or "")
        self._session_id = sessions[-1].get("id")
        return self._session_id

    async def session_id(self, now: float, refresh: float = 30.0) -> str | None:
        """Cached lookup; the viewer rarely changes tab."""
        if self._session_id is None or now - self._checked >= refresh:
            self._checked = now
            return await self.newest_id()
        return self._session_id

    async def put_highlights(self, session_id: str, highlights: list[dict]) -> None:
        """Outline rooms in colour in one viewer tab."""
        await self._transport.request(
            "PUT", f"/api/sessions/{session_id}/highlights", json=highlights
        )

    async def put_route(self, session_id: str, route: dict) -> None:
        """Draw an escape route line in one viewer tab."""
        await self._transport.request("PUT", f"/api/sessions/{session_id}/route", json=route)
