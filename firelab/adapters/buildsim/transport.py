"""How we talk to BuildSim: one connection pool, one error type, one failure rule."""

from typing import Any

import httpx


class BuildSimError(RuntimeError):
    """Anything that went wrong talking to BuildSim, network or HTTP status."""


class Transport:
    """Owns the connection and turns every kind of failure into `BuildSimError`.

    Nothing here knows what any URL means. Change this file to change how we
    talk to BuildSim; change `client.py` to change what we say.
    """

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def aclose(self) -> None:
        """Shut the connection pool down on exit."""
        await self._client.aclose()

    async def request(self, method: str, path: str, **kwargs) -> Any:
        """Make one call and raise `BuildSimError` for every kind of failure."""
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise BuildSimError(f"{method} {path}: {exc}") from exc
        if response.status_code >= 400:
            raise BuildSimError(f"{method} {path}: {response.status_code} {response.text[:200]}")
        if not response.content:
            return None  # a successful PUT usually replies with nothing
        return response.json()
