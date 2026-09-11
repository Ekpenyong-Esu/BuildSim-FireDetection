"""The heartbeat: one tick loop wiring the four zones together.

    WORLD        truth.advance       physics over the building graph
    SENSING      truth.sense         devices corrupt the truth into readings
    INTELLIGENCE intelligence.think  features -> detector -> agent
    ACTUATION    actuation.apply     interlocks -> actuators -> back into the world

This file is only about *when* things happen. *What* happens lives in the
sibling modules, and the state they all work on lives in `state.py`.
"""

from __future__ import annotations

import asyncio
import contextlib
import time

from ...domain.world import UNITS_TO_METRES
from .. import snapshot as snapshot_mod
from . import actuation, building, intelligence, publishing, recording, truth
from .constants import PUBLISH_EVERY, REAL_TICK
from .state import EngineState


class Engine(EngineState):
    """The state, plus the loop that advances it."""

    # --- lifecycle ------------------------------------------------------------

    async def start(self) -> None:
        """Load the building, then start the tick loop running in the background."""
        await building.load(self)
        self.task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """Cancel the loop and close the connection to BuildSim."""
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
        await self.client.aclose()

    def set_running(self, running: bool) -> None:
        """Play or pause simulated time."""
        self.running = running
        self.log("info", "running" if running else "paused")

    def set_clock(self, seconds: float | None = None, factor: float | None = None) -> None:
        """Jump to a time, or change how many simulated seconds pass per real one."""
        if seconds is not None:
            self.now = float(seconds)
        if factor is not None:
            self.config.factor = max(0.1, min(float(factor), 600.0))  # keep it sane

    # --- the tick loop --------------------------------------------------------

    async def _loop(self) -> None:
        """Wakes four times a second and advances the world.

        Real time and simulated time are separate: one real tick may be many
        simulated seconds when the speed factor is turned up.
        """
        last = time.monotonic()
        while True:
            await asyncio.sleep(REAL_TICK)
            wall = time.monotonic()
            elapsed, last = wall - last, wall
            if not self.loaded:
                continue  # no building yet
            if not self.running:
                await self._publish_if_dirty()
                continue
            async with self.lock:  # a tick and an API call must not interleave
                await self._tick(elapsed * self.config.factor)
            self._broadcast()  # push the new snapshot to every open browser

    async def _tick(self, simulated: float) -> None:
        """One pass through all four zones, covering `simulated` seconds."""
        # Break the jump into small steps, so fast-forwarding does not make the
        # physics unstable. Capped at 60 to stay responsive.
        count = max(1, min(int(simulated / self.config.step_seconds), 60))
        dt = simulated / count
        for _ in range(count):
            self.now += dt
            truth.advance(self, dt)
            truth.sense(self, dt)
            truth.expose(self, dt)
        for cmd in intelligence.think(self):
            actuation.apply(self, cmd)
        recording.record(self)
        # Route anyone in a threatened room, then move everyone walking.
        await self.evacuation.plan(
            self.occupants, self.world, actuation.danger(self), self.config.exits
        )
        self.evacuation.advance(
            self.occupants, self.config.walking_speed / UNITS_TO_METRES * simulated
        )
        # Writing to BuildSim is expensive, so it happens far less often than
        # the physics runs.
        if self.now - self.last_publish >= PUBLISH_EVERY * self.config.factor:
            self.last_publish = self.now
            await publishing.publish(self)

    async def _publish_if_dirty(self) -> None:
        """Keep BuildSim in sync while the clock is paused, so people show up."""
        if not self.dirty:
            return
        self.dirty = False
        async with self.lock:
            await publishing.publish(self)
        self._broadcast()

    # --- snapshot for the UI --------------------------------------------------

    def subscribe(self) -> asyncio.Queue:
        """A queue for one browser connection."""
        return self.stream.subscribe()

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Drop a connection that has gone away."""
        self.stream.unsubscribe(queue)

    def _broadcast(self) -> None:
        """Build the snapshot once and hand it to every listener."""
        if self.stream:
            self.stream.send(self.snapshot())

    def rooms(self) -> list[dict]:
        """The room list for the picker."""
        return snapshot_mod.rooms(self.world)

    def snapshot(self) -> dict:
        """The whole simulation as JSON-friendly data for the UI."""
        return snapshot_mod.build(self)
