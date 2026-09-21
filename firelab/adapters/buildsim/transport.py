"""The common way Firelab sends HTTP requests to BuildSim.

This file keeps connection reuse, timeouts, and errors in one place. The app
only needs to handle one error type when BuildSim cannot answer.

This is the only file in firelab that touches the network. Everything above it
(`client.py`, `viewer.py`) says *what* to ask BuildSim; this file only knows
*how*: open one HTTP connection pool, send a request, and turn every way a
request can fail into a single `BuildSimError` so the caller has one thing to
catch.
"""

from typing import Any

import httpx  # the async HTTP library; nothing outside adapters/ may import it (test_layering checks)

# Any error text from BuildSim is cut to this many characters before it goes
# into the journal, so a stack trace from the Go side cannot flood the log.
ERROR_TEXT_LIMIT = 200


class BuildSimError(RuntimeError):
    """Anything that went wrong talking to BuildSim, network or HTTP status.

    One type on purpose: the engine does not care whether BuildSim is down,
    slow, or answered 404. In every case it marks itself disconnected, logs the
    message, and waits for a Reload. The message says which call failed and why.
    """


class Transport:
    """Owns the connection and turns every kind of failure into `BuildSimError`.

    Nothing here knows what any URL means. Change this file to change how we
    talk to BuildSim; change `client.py` to change what we say.
    """

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        """Keep one httpx pool for every call made through this object.

        `timeout` is per call, in seconds. BuildSim normally answers in
        milliseconds, so ten seconds means "it is gone", not "it is busy".
        """
        self.base_url = base_url.rstrip("/")  # e.g. "http://127.0.0.1:9090"; shown in the panel's header
        # One pool for the life of the process: connections are reused across
        # calls instead of being opened and closed a hundred times a second.
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)  # closed by aclose()

    async def aclose(self) -> None:
        """Shut the connection pool down on exit."""
        await self._client.aclose()

    async def request(self, method: str, path: str, **kwargs) -> Any:
        """Make one call and raise `BuildSimError` for every kind of failure.

        `method` is GET, PUT, POST or DELETE; `path` is relative to the base
        URL, e.g. "/api/room-layers"; `kwargs` go straight to httpx (`json=`
        for a body, `params=` for a query string). Returns the decoded JSON
        reply, or None when BuildSim sent an empty body.
        """
        # Failure 1: no answer at all. Connection refused, DNS, timeout, a
        # dropped socket: httpx raises for all of them, and they all mean the
        # same thing to us, that BuildSim is not there.
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise BuildSimError(f"{method} {path}: {exc}") from exc
        # Failure 2: an answer that says no. 4xx is our mistake (a bad room name,
        # a malformed body), 5xx is BuildSim's. Either way the call did not do
        # what we asked, so it is an error, with BuildSim's own words attached.
        if response.status_code >= 400:
            raise BuildSimError(
                f"{method} {path}: {response.status_code} {response.text[:ERROR_TEXT_LIMIT]}"
            )
        # Success. A PUT or DELETE usually replies with an empty body, which is
        # not JSON, so it is reported as None rather than passed to the parser.
        if not response.content:
            return None
        return response.json()
