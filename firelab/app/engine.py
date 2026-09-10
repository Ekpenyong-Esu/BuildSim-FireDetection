"""The simulation engine: one tick loop wiring the four zones together.

    WORLD        physics.step over the building graph
    SENSING      devices corrupt the truth into readings
    INTELLIGENCE features -> detector -> agent (readings only)
    ACTUATION    commands -> interlocks -> actuators -> back into the world

Only this module holds mutable state, and only it talks to BuildSim.
"""

import asyncio
import contextlib
import time
from random import Random

from ..adapters import publisher
from ..adapters.buildsim import BuildSim, BuildSimError, UNITS_TO_METRES
from ..adapters.world_builder import build_world, derive_exits, page_bounds
from ..domain import agent as agent_mod
from ..domain import interlocks, occupants as occupants_mod, physics, sensing, sources, tenability
from ..domain.detector import FusionRule
from ..domain.features import Features, Window, extract
from ..domain.history import History
from ..domain.scoring import Scoreboard
from . import presets as presets_mod
from . import snapshot as snapshot_mod
from .config import Config
from .evacuation import Evacuation, path_length

REAL_TICK = 0.25  # seconds of wall clock between engine ticks
PUBLISH_EVERY = 1.0  # simulated seconds between BuildSim writes
MAX_SENSOR_WRITES = 24  # per publish, to keep BuildSim responsive


class Engine:
    """Everything mutable in one object: the world, the devices, the agents.

    Keeping the state here means every other module can be a pure function of
    its inputs, which is why they are all so easy to test.
    """

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.client = BuildSim(self.config.buildsim_url)
        self.detector = FusionRule()  # swap this line to try a trained model
        self.evacuation = Evacuation(self.client)
        self.rng = Random(self.config.seed)  # one seeded source of randomness

        # The building, as loaded from BuildSim.
        self.world = physics.World()
        self.entries: dict[str, dict] = {}
        self.floors: dict[str, dict] = {}
        self.bounds: dict[str, tuple[float, float]] = {}
        self.connected = False
        self.loaded = False

        # The run itself.
        self.now = 8 * 3600.0  # simulated seconds since midnight
        self.running = False
        self.sources: list[sources.Source] = []
        self.devices: dict[str, sensing.Device] = {}
        self.windows: dict[str, Window] = {}  # recent readings, per room
        self.features: dict[str, Features] = {}
        self.probabilities: dict[str, float] = {}
        self.agents: dict[str, agent_mod.RoomAgent] = {}
        self.occupants: list[occupants_mod.Occupant] = []
        self.doors: dict[str, str] = {}  # space key -> "open" | "closed"
        self.journal: list[dict] = []
        self.score = Scoreboard()
        self.history = History()

        # Bookkeeping for the loop and for talking to BuildSim.
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()  # a tick and an API call must not interleave
        self._last_publish = -1e9
        self._dirty = False  # something changed while paused; publish once
        self._pending_writes: dict[str, float] = {}  # sensor values still to send
        self._last_route: list[dict] | None = None
        self._last_highlights: list[dict] | None = None
        self._subscribers: set[asyncio.Queue] = set()  # open browser connections

    # --- lifecycle ------------------------------------------------------------

    async def start(self) -> None:
        """Load the building, then start the tick loop running in the background."""
        await self.load()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """Cancel the loop and close the connection to BuildSim."""
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        await self.client.aclose()

    async def load(self) -> None:
        """Fetch floors from BuildSim and rebuild the world."""
        self.connected = await self.client.health()
        if not self.connected:
            self.log("error", "BuildSim is not reachable at " + self.config.buildsim_url)
            return
        floors = {}
        for level in self.config.levels:
            try:
                floors[level] = await self.client.floor(level)
            except BuildSimError as exc:
                self.log("error", f"could not load {level}: {exc}")
        if not floors:
            return
        self.floors = floors
        self.bounds = page_bounds(floors)
        self.world, self.entries = build_world(floors)
        self.config.exits = derive_exits(floors, self.config.exits)
        self.loaded = True
        self.log(
            "info",
            f"loaded {len(self.world.spaces)} spaces and "
            f"{len(self.world.couplings)} couplings from {', '.join(floors)}",
        )
        self.place_occupants(self.config.population)

    # --- public commands ------------------------------------------------------

    def log(self, kind: str, message: str) -> None:
        """Add one line to the journal shown in the UI."""
        self.journal.append({"t": round(self.now, 1), "kind": kind, "message": message})
        del self.journal[:-200]  # keep only the last 200 lines

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

    def ignite(self, space: str, kind: str, growth: str, delay: float, peak_kw: float) -> dict:
        """Schedule a fire or a nuisance. `delay` lets it start later."""
        if space not in self.world.spaces:
            raise KeyError(space)
        if kind not in sources.KINDS:
            raise ValueError(kind)
        source = sources.Source(
            id=f"src-{len(self.sources) + 1}-{int(self.now)}",
            kind=kind,
            space=space,
            t_start=self.now + max(0.0, delay),
            growth=growth,
            peak_kw=peak_kw,
        )
        self.sources.append(source)
        self.log("scenario", f"{kind} source scheduled in {self.world.spaces[space].name}")
        return source.__dict__

    def remove_source(self, source_id: str) -> None:
        """Put a source out. What it already emitted still has to disperse."""
        self.sources = [s for s in self.sources if s.id != source_id]

    def apply_preset(self, preset_id: str, space: str) -> dict:
        """Instrument the room, then set up the situation described by the preset."""
        preset = presets_mod.BY_ID.get(preset_id)
        if preset is None:
            raise KeyError(preset_id)
        if space not in self.world.spaces:
            raise KeyError(space)
        # Instrument the room and its neighbours, so cross-room agreement works.
        self.deploy([space, *self._neighbours_of(space)], list(sensing.MODALITIES))
        if preset.fault != "none":
            device_id = f"fl-{space.replace('/', '-')}-smoke"
            if device_id in self.devices:
                self.set_fault(device_id, preset.fault)
        source = None
        if preset.kind:  # "drifting-sensor" has no source: nothing is burning
            source = self.ignite(space, preset.kind, preset.growth, preset.delay, preset.peak_kw)
        self.log("scenario", f"preset \"{preset.name}\" in {self.world.spaces[space].name}")
        return {"preset": preset.id, "source": source}

    def _neighbours_of(self, space: str) -> list[str]:
        """Rooms joined to this one by a doorway."""
        return [
            link.b if link.a == space else link.a
            for link in self.world.couplings
            if space in (link.a, link.b)
        ]

    def deploy(self, spaces: list[str], modalities: list[str]) -> int:
        """Install sensors. Deploying is what makes a room monitored at all."""
        count = 0
        for key in spaces:
            if key not in self.world.spaces:
                continue
            for modality in modalities:
                if modality not in sensing.MODALITIES:
                    continue
                device_id = f"fl-{key.replace('/', '-')}-{modality}"
                if device_id in self.devices:
                    continue  # already installed
                device = sensing.Device.create(device_id, key, modality)
                device.interval = self.config.sensors.interval
                device.noise *= self.config.sensors.noise_scale
                device.next_sample = self.now
                self.devices[device_id] = device
                # A monitored room also needs somewhere to keep readings and an
                # agent to hold its state.
                self.windows.setdefault(key, Window(space=key))
                self.agents.setdefault(key, agent_mod.RoomAgent(space=key, since=self.now))
                count += 1
        self.log("info", f"deployed {count} devices")
        self._dirty = True
        return count

    def undeploy(self, spaces: list[str]) -> int:
        """Remove the sensors and everything derived from them."""
        targets = {d.id for d in self.devices.values() if d.space in spaces}
        for device_id in targets:
            del self.devices[device_id]
        for key in spaces:
            self.windows.pop(key, None)
            self.agents.pop(key, None)
            self.probabilities.pop(key, None)
            self.features.pop(key, None)
        return len(targets)

    def set_fault(self, device_id: str, fault: str) -> None:
        """Break one sensor on purpose, to see whether the rest cope."""
        device = self.devices.get(device_id)
        if device is None or fault not in sensing.FAULTS:
            raise KeyError(device_id)
        device.fault = fault
        device.drift = 0.0  # start the drift from wherever it is now
        self.log("fault", f"{device_id} -> {fault}")

    def command(self, kind: str, space: str, value: str) -> dict:
        """Manual override from the UI. It still goes through the interlocks."""
        cmd = agent_mod.Command(kind=kind, space=space, value=value, reason="manual override")
        verdict = self._apply(cmd, manual=True)
        return {"allowed": verdict.allowed, "reason": verdict.reason}

    def reset(self) -> None:
        """Back to a quiet building. Keeps the floor plans and the sensors."""
        self.world.reset()
        self.sources.clear()
        self.probabilities.clear()
        self.features.clear()
        for window in self.windows.values():
            window.series.clear()
        for device in self.devices.values():
            device.internal = 20.0 if device.modality == "temperature" else 0.0
            device.reading = None
            device.drift = 0.0
            device.history.clear()
        for room_agent in self.agents.values():
            room_agent.state = "NORMAL"
            room_agent.probability = 0.0
            room_agent.above_since = None
            room_agent.below_since = None
        self.doors.clear()
        self.evacuation.reset()
        self.score.clear()
        self.history.clear()
        self._last_route = None
        self._last_highlights = None
        self.place_occupants(self.config.population)
        self.log("info", "simulation reset")

    def place_occupants(self, population: dict[str, int]) -> None:
        """Scatter people through the building again."""
        self.occupants = occupants_mod.place(self.world.spaces.values(), population, self.rng)
        self._dirty = True

    def reseed(self) -> None:
        """Restart the randomness, so the next run repeats exactly."""
        self.rng = Random(self.config.seed)

    # --- the tick loop --------------------------------------------------------

    async def _loop(self) -> None:
        """The heartbeat. Wakes four times a second and advances the world.

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
            async with self._lock:
                simulated = elapsed * self.config.factor
                # Break the jump into small steps, so fast-forwarding does not
                # make the physics unstable. Capped at 60 to stay responsive.
                steps = max(1, min(int(simulated / self.config.step_seconds), 60))
                dt = simulated / steps
                for _ in range(steps):
                    self.now += dt
                    self._physics(dt)  # WORLD
                    self._sense(dt)  # SENSING
                    self._expose(dt)
                self._think()  # INTELLIGENCE and ACTUATION
                self._record()
                # Route anyone in a threatened room, then move everyone walking.
                await self.evacuation.plan(
                    self.occupants, self.world, self._danger(), self.config.exits
                )
                self.evacuation.advance(
                    self.occupants, self.config.walking_speed / UNITS_TO_METRES * simulated
                )
                # Writing to BuildSim is expensive, so it happens far less often
                # than the physics runs.
                if self.now - self._last_publish >= PUBLISH_EVERY * self.config.factor:
                    self._last_publish = self.now
                    await self._publish()
            self._broadcast()  # push the new snapshot to every open browser

    async def _publish_if_dirty(self) -> None:
        """Keep BuildSim in sync while the clock is paused, so people show up."""
        if not self._dirty:
            return
        self._dirty = False
        async with self._lock:
            await self._publish()
        self._broadcast()

    def _physics(self, dt: float) -> None:
        """WORLD: work out what every source is emitting, then advance the world."""
        emissions: dict[str, tuple[float, float, float]] = {}
        for source in self.sources:
            heat, smoke, co = sources.emission(source, self.now)
            if heat == 0.0 and smoke == 0.0 and co == 0.0:
                continue  # not lit yet, or burnt out
            # Two sources in one room simply add up.
            prev = emissions.get(source.space, (0.0, 0.0, 0.0))
            emissions[source.space] = (prev[0] + heat, prev[1] + smoke, prev[2] + co)
        physics.step(self.world, emissions, dt)

    def _sense(self, dt: float) -> None:
        """SENSING: let each device look at the truth and report what it thinks."""
        for device in self.devices.values():
            space = self.world.spaces.get(device.space)
            if space is None:
                continue
            truth = getattr(space, device.modality)  # the real temperature/smoke/CO
            value = sensing.sample(device, truth, self.now, dt, self.rng)
            if value is None:
                continue  # not due yet, or the device is dead
            self.windows.setdefault(device.space, Window(space=device.space)).add(
                device.modality, self.now, value
            )
            self._pending_writes[device.id] = value

    def _expose(self, dt: float) -> None:
        """Add this step's CO dose to everyone still inside.

        Dose is carried by the person, not the room: walking out through a smoke
        logged corridor costs you, and it keeps costing you afterwards.
        """
        for occupant in self.occupants:
            if occupant.safe:
                continue
            space = self.world.spaces.get(occupant.space)
            if space is not None:
                occupant.fed += tenability.fed_increment(space.co, dt)

    def _think(self) -> None:
        """INTELLIGENCE: features, then P(fire), then the state machine.

        Note what this method touches: windows of readings, never `space.smoke`.
        The truth is one attribute away and deliberately not used.
        """
        neighbours = self._neighbour_readings()
        for key, window in self.windows.items():
            features = extract(window, neighbours.get(key, []))
            self.features[key] = features
            probability = self.detector.probability(features)
            self.probabilities[key] = probability

            room_agent = self.agents.setdefault(
                key, agent_mod.RoomAgent(space=key, since=self.now)
            )
            before = room_agent.state
            commands = agent_mod.update(room_agent, probability, self.now, self._thresholds())
            if room_agent.state != before:
                name = self.world.spaces[key].name
                self.log("agent", f"{name}: {before} -> {room_agent.state}")
            if not self.config.response.auto:
                continue  # supervised mode: the commands are dropped
            for cmd in commands:
                self._apply(cmd)  # ACTUATION

        self.score.update(
            self.now,
            self.sources,
            {key: a.state for key, a in self.agents.items()},
            evacuating=sum(1 for o in self.occupants if o.status == "evacuating"),
            inside=sum(1 for o in self.occupants if not o.safe),
        )

    def _record(self) -> None:
        """Save a row of truth-and-reading for every monitored room, now and then."""
        if not self.history.due(self.now):
            return
        rows = {}
        for key in self.windows:
            space = self.world.spaces.get(key)
            if space is None:
                continue
            reading = self.features.get(key)
            rows[key] = [
                round(space.temperature, 2),
                round(space.smoke, 4),
                round(space.co, 1),
                round(reading.temperature, 2) if reading else None,
                round(reading.smoke, 4) if reading else None,
                round(reading.co, 1) if reading else None,
                round(self.probabilities.get(key, 0.0), 3),
            ]
        self.history.record(self.now, rows)

    def _thresholds(self) -> agent_mod.Thresholds:
        """Copy the live UI settings into the plain object the agent expects."""
        r = self.config.response
        return agent_mod.Thresholds(
            investigate=r.investigate,
            pre_alarm=r.pre_alarm,
            confirm=r.confirm,
            clear=r.clear,
            dwell_pre_alarm=r.dwell_pre_alarm,
            dwell_confirm=r.dwell_confirm,
            dwell_clear=r.dwell_clear,
        )

    def _neighbour_readings(self) -> dict[str, list[float]]:
        """For each monitored room, the smoke its monitored neighbours report."""
        readings: dict[str, list[float]] = {}
        for link in self.world.couplings:
            # Look at each doorway from both sides.
            for a, b in ((link.a, link.b), (link.b, link.a)):
                window = self.windows.get(b)
                if window is None or a not in self.windows:
                    continue  # one side has no sensors, so it cannot corroborate
                readings.setdefault(a, []).append(window.latest("smoke"))
        return readings

    # --- actuation ------------------------------------------------------------

    def _apply(self, cmd: agent_mod.Command, manual: bool = False) -> interlocks.Verdict:
        """Check one command against the interlocks and, if allowed, carry it out.

        This is the single door between deciding and doing. Agent commands and
        button presses both come through here.
        """
        space = self.world.spaces.get(cmd.space)
        if space is None:
            return interlocks.Verdict(False, "unknown space")

        occupants = sum(1 for o in self.occupants if o.space == cmd.space and not o.safe)
        on_route = any(cmd.space in o.route_spaces for o in self.occupants)
        verdict = interlocks.check(cmd, space.temperature, occupants, on_route)
        if not verdict.allowed:
            self.log("interlock", f"blocked {cmd.kind}={cmd.value} in {space.name}: {verdict.reason}")
            return verdict

        if cmd.kind == "sprinkler":
            space.sprinkler = cmd.value == "on"
        elif cmd.kind == "fire_door":
            self.doors[cmd.space] = cmd.value
            # A closed door does not seal: it still leaks about 15%.
            openness = 1.0 if cmd.value == "open" else 0.15
            for link in self.world.couplings:
                if cmd.space in (link.a, link.b):
                    link.openness = openness
        elif cmd.kind == "evacuate":
            evacuating = cmd.value == "start"
            for occupant in self.occupants:
                if not occupant.safe:
                    occupant.status = "evacuating" if evacuating else "idle"

        prefix = "manual" if manual else "auto"
        self.log("actuator", f"{prefix} {cmd.kind}={cmd.value} in {space.name}")
        self._dirty = True
        return verdict

    # --- occupants ------------------------------------------------------------

    def _danger(self) -> set[str]:
        """Rooms people should be got out of. Pre-alarm counts: waiting costs lives."""
        return {
            key
            for key, room_agent in self.agents.items()
            if room_agent.state in ("CONFIRMED", "SUPPRESSED", "PRE_ALARM")
        }

    # --- publishing -----------------------------------------------------------

    async def _publish(self) -> None:
        """Send the whole visual state to BuildSim in one burst of parallel calls."""
        if not self.connected:
            return
        states = {key: a.state for key, a in self.agents.items() if a.state != "NORMAL"}
        burning = {
            s.space for s in self.sources if s.kind in ("flaming", "smouldering", "cooking")
        } & set(self.world.spaces)
        # Only draw flames once there is visible smoke, not the instant it lights.
        burning = {key for key in burning if self.world.spaces[key].smoke > 0.05}

        tasks = [
            self.client.put_room_layers(publisher.room_layers(self.world, self.probabilities)),
            self.client.put_effects(publisher.effects(self.world, burning)),
            self.client.put_alerts(publisher.alerts(self.world, states, self.probabilities)),
            self.client.put_entities(
                publisher.entities(
                    self.world, self.occupants, int(PUBLISH_EVERY * 1000), self.bounds
                )
            ),
            self.client.put_occupancy(publisher.occupancy(self.world, self.occupants)),
            self.client.put_doors(publisher.doors(self.world, self.doors)),
        ]
        tasks.extend(await self._session_writes(states))
        tasks.extend(self._sensor_writes())

        # All at once, and the first failure marks us disconnected.
        for result in await asyncio.gather(*tasks, return_exceptions=True):
            if isinstance(result, BuildSimError):
                self.connected = False
                self.log("error", str(result))
                break

    async def _session_writes(self, states: dict[str, str]) -> list:
        """The viewer re-frames its camera on every route it is sent and
        repaints on every highlight, so only push these when they change."""
        session_id = await self.client.viewer_session_id(time.monotonic())
        if not session_id:
            return []
        writes = []
        highlights = publisher.highlights(self.world, states)
        if highlights != self._last_highlights:
            self._last_highlights = highlights
            writes.append(self.client.put_session_highlights(session_id, highlights))
        route = self.evacuation.display_route
        if route and route != self._last_route:
            self._last_route = route
            writes.append(self.client.put_session_route(session_id, self._route_payload(route)))
        return writes

    def _sensor_writes(self) -> list:
        """Push a few pending readings into BuildSim's sensor labels.

        Only a handful per publish: with 2868 devices, sending them all would
        bury BuildSim.
        """
        writes = []
        for device_id, value in list(self._pending_writes.items())[:MAX_SENSOR_WRITES]:
            del self._pending_writes[device_id]
            writes.append(self.client.set_sensor_value(f"{device_id}-val", f"{value:.3f}"))
        return writes

    @staticmethod
    def _route_payload(path: list[dict]) -> dict:
        """A route in BuildSim's shape, with the distance converted to metres."""
        return {"path": path, "distance": round(path_length(path) * UNITS_TO_METRES, 1)}

    async def register_equipment(self) -> int:
        """Mirror every sensing device into BuildSim's equipment tree."""
        if not self.connected:
            return 0
        items = publisher.equipment(self.world, self.devices.values())
        if not items:
            return 0
        try:
            result = await self.client.create_equipment_bulk(items)
        except BuildSimError as exc:
            self.log("error", f"equipment registration failed: {exc}")
            return 0
        created = (result or {}).get("created", 0)
        self.log("info", f"registered {created} equipment items in BuildSim")
        return created

    # --- snapshot for the UI --------------------------------------------------

    def subscribe(self) -> asyncio.Queue:
        """A queue for one browser connection. Small on purpose: see `_broadcast`."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=4)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Drop a connection that has gone away."""
        self._subscribers.discard(queue)

    def _broadcast(self) -> None:
        """Give every connected browser the newest snapshot.

        A slow client is not allowed to hold the engine up: if its queue is full
        the oldest snapshot is thrown away. Stale state is worse than no state.
        """
        if not self._subscribers:
            return
        snapshot = self.snapshot()
        for queue in list(self._subscribers):
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(snapshot)

    def rooms(self) -> list[dict]:
        """The room list for the picker."""
        return snapshot_mod.rooms(self.world)

    def snapshot(self) -> dict:
        """The whole simulation as JSON-friendly data for the UI."""
        return snapshot_mod.build(self)
