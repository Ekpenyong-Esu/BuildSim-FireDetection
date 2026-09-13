"""Fan-out of snapshots to the open browser connections behind /api/events."""

from __future__ import annotations

import asyncio
import contextlib


class Broadcaster:
    """One small queue per connected browser.

    A slow client is not allowed to hold the engine up: when its queue is full
    the oldest snapshot is thrown away. Stale state is worse than no state.
    """

    def __init__(self, depth: int = 4) -> None:
        """How many snapshots a slow browser may fall behind before we drop."""
        self._depth = depth
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        """A queue for one browser connection."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._depth)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Drop a connection that has gone away."""
        self._subscribers.discard(queue)

    def send(self, snapshot: dict) -> None:
        """Give every connected browser the newest snapshot."""
        for queue in list(self._subscribers):
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(snapshot)

    def __bool__(self) -> bool:
        """True when at least one browser is listening.

        Lets the engine write `if self.stream:` and skip building a snapshot
        nobody would receive. Building one costs a pass over every room.
        """
        return bool(self._subscribers)
