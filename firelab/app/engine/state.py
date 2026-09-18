"""Every mutable value in the simulation, and nothing that acts on them.

Splitting the state out from the tick loop is what lets each phase module take
the engine as a plain argument without importing the engine that calls it.
"""

from __future__ import annotations

import asyncio
from random import Random

from ...adapters.buildsim import BuildSim
from ...domain import agent as agent_mod
from ...domain import occupants as occupants_mod
from ...domain import sensing, sources
from ...domain import world as world_mod
from ...domain.detector import FusionRule
from ...domain.features import Features, Window
from ...domain.history import History
from ...domain.scoring import Scoreboard
from ..config import Config
from ..evacuation import Evacuation
from .streaming import Broadcaster


class EngineState:
    """Everything mutable in one object: the world, the devices, the agents.

    Keeping the state here means every other module can be a pure function of
    its inputs, which is why they are all so easy to test.
    """

    def __init__(self, config: Config | None = None) -> None:
        """Build a fresh, empty run ready to be loaded and started."""
        self.config = config or Config()  # the settings; edited live through PUT /api/config
        self.client = BuildSim(self.config.buildsim_url)  # the only way out to BuildSim
        self.detector = FusionRule()  # swap this line to try a trained model
        self.evacuation = Evacuation(self.client)  # routes people out; keeps the drawn route
        self.rng = Random(self.config.seed)  # one seeded source of randomness

        # The building, as loaded from BuildSim.
        self.world = world_mod.World()  # every room and doorway, with the true state of each
        self.floors: dict[str, dict] = {}  # the raw floor plans, by level, as BuildSim sent them
        self.bounds: dict[str, tuple[float, float]] = {}  # level -> page (width, height), to keep markers on the plan
        self.connected = False  # BuildSim answered the last call; False stops publishing
        self.loaded = False  # a building is in `world`; False makes the loop idle

        # The run itself.
        self.now = 8 * 3600.0  # simulated seconds since midnight
        self.running = False  # the clock is playing
        self.sources: list[sources.Source] = []  # every fire and nuisance lit so far
        self.devices: dict[str, sensing.Device] = {}  # every sensor deployed, by device id
        self.windows: dict[str, Window] = {}  # recent readings, per room
        self.features: dict[str, Features] = {}  # room key -> the latest feature summary
        self.probabilities: dict[str, float] = {}  # room key -> the latest P(fire)
        self.agents: dict[str, agent_mod.RoomAgent] = {}  # room key -> its alarm ladder; only monitored rooms have one
        self.occupants: list[occupants_mod.Occupant] = []  # everyone in the building, out or not
        self.doors: dict[str, str] = {}  # space key -> "open" | "closed"
        self.blocks: dict[tuple[str, str, str], str] = {}  # held command -> why, for the log
        self.journal: list[dict] = []  # the last 200 log lines, oldest first; the panel shows 40
        self.score = Scoreboard()  # detections, misses, false alarms, and the evacuation clock
        self.history = History()  # truth beside reading, per room, every 5 s, for charts and the CSV

        # Bookkeeping for the loop and for talking to BuildSim.
        self.pending_writes: dict[str, float] = {}  # sensor values still to send
        self.last_route: tuple[str, list[dict], str] | None = None  # tab, route, storey
        self.last_highlights: list[dict] | None = None  # what the viewer was last sent; None = never
        self.task: asyncio.Task | None = None  # the running tick loop, so stop() can cancel it
        self.lock = asyncio.Lock()  # a tick and an API call must not interleave
        self.last_publish = -1e9  # simulated time BuildSim was last drawn; long ago, so the first tick draws
        self.dirty = False  # something changed while paused; publish once
        self.stream = Broadcaster()  # the open /api/events connections, one queue each

    def log(self, kind: str, message: str) -> None:
        """Add one line to the journal shown in the UI."""
        self.journal.append({"t": round(self.now, 1), "kind": kind, "message": message})
        del self.journal[:-200]  # keep only the last 200 lines

    def mark_dirty(self) -> None:
        """Something changed while paused: publish once more so the UI catches up."""
        self.dirty = True
