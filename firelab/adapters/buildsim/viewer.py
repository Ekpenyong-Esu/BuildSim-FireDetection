"""Keep track of which BuildSim viewer tab should receive display updates.

The publisher uses this when more than one viewer tab is open. It chooses the
most recently active tab for room highlights and escape routes.

Most of what firelab sends BuildSim is about the *building* (heat maps, people,
doors) and shows in every viewer tab at once. Two things are different: the
coloured room outlines (highlights) and the escape-route line are drawn *per
tab*, because BuildSim treats them as part of a viewer session, alongside that
tab's camera. So something has to remember which tab the user is looking at.
That cache is the only state the BuildSim adapter holds.
"""

from .transport import Transport

# How often, in seconds, to ask BuildSim again which tab is active. The user
# rarely switches tabs, and each lookup is one round trip per publish.
SESSION_REFRESH = 30.0


class ViewerSessions:
    """Tracks the active viewer tab and draws into it.

    A "session" is one open browser tab of BuildSim's viewer. BuildSim creates
    one when a tab connects and forgets it when the tab closes; each has an id
    and a `last_ws_active` timestamp that ticks while the tab is alive. When
    several tabs are open, the most recently active one is taken to be the
    one the user is watching.
    """

    def __init__(self, transport: Transport) -> None:
        """Borrow the shared transport; the viewer has no connection of its own."""
        self._transport = transport  # shared with the client
        self._session_id: str | None = None  # the tab being drawn into; None until one is found
        self._checked = -1e9  # when the tab was last looked up; long ago, so the first lookup always runs

    async def all(self) -> list[dict]:
        """Every viewer tab BuildSim currently knows about.

        `GET /api/sessions` answers with a list of session objects (id,
        viewport, highlights, route, last_ws_active, ...). An empty list means
        nobody has the viewer open, which is normal, not an error.
        """
        return await self._transport.request("GET", "/api/sessions") or []

    async def newest_id(self) -> str | None:
        """The most recently active tab: the one the user is probably looking at.

        Always asks BuildSim; `session_id()` is the cached version to call from
        the publish loop. Also updates the cache, and clears it when no tab is
        open, so nothing is drawn into a tab that has gone.
        """
        sessions = await self.all()
        if not sessions:
            self._session_id = None
            return None
        # `last_ws_active` is an ISO timestamp, so sorting the strings sorts by
        # time; a missing one sorts first and so is never chosen over a live tab.
        sessions.sort(key=lambda s: s.get("last_ws_active") or "")
        self._session_id = sessions[-1].get("id")
        return self._session_id

    async def session_id(self, now: float, refresh: float = SESSION_REFRESH) -> str | None:
        """Cached lookup; the viewer rarely changes tab.

        `now` is a monotonic clock in seconds (the caller passes
        `time.monotonic()`), used only to decide whether the cache is stale.
        Asks BuildSim again when no tab is known yet, or every `refresh`
        seconds, so a newly opened tab is found within half a minute.
        """
        if self._session_id is None or now - self._checked >= refresh:
            self._checked = now
            return await self.newest_id()
        return self._session_id

    # --- drawing into a tab ---------------------------------------------------
    # Both calls replace what the tab had before: sending an empty list, or a
    # route with no path, is how the outlines or the line are erased.

    async def put_highlights(self, session_id: str, highlights: list[dict]) -> None:
        """Outline rooms in colour in one viewer tab.

        Each item is {"level", "room", "color", "opacity"}; the colours come
        from the agent's alarm state (see `publisher/beliefs.py`).
        """
        await self._transport.request(
            "PUT", f"/api/sessions/{session_id}/highlights", json=highlights
        )

    async def put_route(self, session_id: str, route: dict) -> None:
        """Draw an escape route line in one viewer tab.

        `route` is {"path": [{"name", "level", "x", "y"}, ...], "distance": m},
        built by `publisher/routes.py`. The viewer re-frames its camera on
        every route it receives, which is why the publisher only sends one
        when it has changed.
        """
        await self._transport.request("PUT", f"/api/sessions/{session_id}/route", json=route)
