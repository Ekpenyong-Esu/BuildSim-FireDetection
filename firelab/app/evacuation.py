"""Evacuation: find escape routes and walk people along them.

The only reason this is not in `domain/` is the route lookup, which is a
network call. Everything else here delegates to `domain.occupants`.
"""

from ..adapters.buildsim import BuildSim, BuildSimError
from ..adapters.publisher import path_length
from ..adapters.walkways import STAIR_COST, Walkways
from ..adapters.world_builder import key_of
from ..domain import occupants as occupants_mod
from ..domain.world import World


class Evacuation:
    """Works out where people should go, and moves them there tick by tick."""

    def __init__(self, client: BuildSim) -> None:
        """Borrow the BuildSim client that knows how to ask for a route."""
        self.client = client  # asked for a route only when firelab's own map finds no clear one
        # The walkable graph, once the building is loaded. It is what finds the
        # way round a burning corridor, which BuildSim's router cannot.
        self.walkways: Walkways | None = None
        self.display_route: list[dict] = []  # the one route drawn in the viewer
        self.display_level = ""  # which storey that route is on
        # Everyone leaving the same room takes the same way out, so the answer is
        # cached instead of asking BuildSim once per person. The danger it was
        # worked out against is kept with it: when the fire moves, it is stale.
        self._cache: dict[str, tuple[list[dict], frozenset[str]]] = {}

    def reset(self) -> None:
        """Forget every planned route, ready for a fresh run."""
        self._cache.clear()
        self.display_route = []
        self.display_level = ""

    async def plan(
        self,
        people: list[occupants_mod.Occupant],
        world: World,
        danger: set[str],
        exits: dict[str, list[str]],
    ) -> None:
        """Give every threatened occupant a way out, and keep it up to date."""
        if not danger:
            # The alarm is over. A line stays up only while somebody is still
            # walking it; after that it is a leftover.
            if not self._anyone_walking(people):
                self._clear_display()
            return
        for occupant in people:
            if occupant.safe:
                continue
            # Once someone starts evacuating they keep going, even if their room
            # is later declared safe.
            if occupant.status != "evacuating" and occupant.space not in danger:
                continue
            occupant.status = "evacuating"
            level = occupant.space.split("/")[0]

            if occupant.route:
                # The room they are standing in is not "ahead": it is usually the
                # one alight, and leaving it is the whole point.
                ahead = {k for k in occupant.route_spaces if k and k != occupant.space}
                crossing = len(ahead & danger)
                if not crossing:
                    continue  # their way out is still clear; let them walk it
                candidate = await self._path(occupant.space, world, danger, exits)
                # Only take somebody off a route they are already walking if the
                # replacement is genuinely safer. Swapping for an equally smoky
                # one restarts them at the beginning every tick, which is how a
                # corridor full of people ends up jogging on the spot.
                if not candidate or self._hazard(
                    world, level, candidate, danger, occupant.space
                ) >= crossing:
                    continue
                path = candidate
            else:
                path = await self._path(occupant.space, world, danger, exits)
                if not path:
                    occupant.status = "no route"  # genuinely trapped: counts against the run
                    continue

            # Two parallel lists: where to walk, and which room that point is in.
            occupant.route = [[node["x"], node["y"]] for node in path]
            occupant.route_spaces = [self._space_key(world, level, node) for node in path]

        # Drawn for as long as the alarm lasts, not just while people walk. At
        # speed the whole building is out within seconds, and taking the line
        # down then meant it flashed up and was gone before anyone saw it.
        await self._choose_display_route(world, danger, exits)

    @staticmethod
    def _anyone_walking(people: list[occupants_mod.Occupant]) -> bool:
        return any(o.status == "evacuating" and not o.safe for o in people)

    def _clear_display(self) -> None:
        self.display_route = []
        self.display_level = ""

    async def _choose_display_route(
        self, world: World, danger: set[str], exits: dict[str, list[str]]
    ) -> None:
        """Pick the one route the viewer draws: the way out of the fire.

        Three ways to get this wrong, and this code has been all of them. Drawing
        whichever route was worked out last picked whoever happened to be planned
        last, usually somebody two floors away. Drawing only an occupant's route
        from inside a burning room drew nothing: forty people in nine hundred
        rooms means nobody is normally standing in it. And drawing the occupant
        route nearest the fire fell back on alphabetical order whenever nobody
        started next door, which put the line at the far end of the wing.

        So the route is worked out from the fire itself, whether or not anyone
        is standing in it: from its centre, the alarming room with the most
        alarming neighbours, ties broken by name so the line stays put. Only if
        no burning room has a way out at all is an occupant's route drawn
        instead, the one starting nearest the fire.

        Routes are asked for again rather than read straight from the cache:
        once everybody is out nothing else re-plans them, and a line worked out
        before the fire spread would go on being drawn through the new fire.
        """
        if not self._cache:
            return  # nobody was ever sent anywhere, so there is nothing to show
        links = world.adjacency()
        centre_first = sorted(danger, key=lambda key: (-len(links.get(key, set()) & danger), key))
        for origin in centre_first:
            path = await self._path(origin, world, danger, exits)
            if path:
                self.display_route = path
                self.display_level = origin.split("/")[0]
                return

        adjacent: set[str] = set()
        for key in danger:
            adjacent |= links.get(key, set())

        def nearness(origin: str) -> tuple[int, str]:
            if origin in danger:
                return (0, origin)
            return (1, origin) if origin in adjacent else (2, origin)

        origin = min(self._cache, key=nearness)
        path = await self._path(origin, world, danger, exits)  # the cache, unless the fire moved
        if path:
            self.display_route = path
            self.display_level = origin.split("/")[0]

    def advance(self, people: list[occupants_mod.Occupant], distance: float) -> None:
        """Move everyone who is evacuating `distance` further along their route."""
        for occupant in people:
            if occupant.status != "evacuating" or occupant.safe or not occupant.route:
                continue
            occupants_mod.advance(occupant, distance * occupant.speed)

    async def _path(
        self, space_key: str, world: World, danger: set[str], exits: dict[str, list[str]]
    ) -> list[dict]:
        """The safest way out, and failing that the least bad one.

        A clear route always wins. But a corridor beside the fire alarms within
        a minute or two, and in this building one corridor is often the only way
        out of a whole wing — so refusing every route that touches danger walls
        people in and leaves them standing still while the fire grows. Nobody
        stays put because the way out is smoky; they move, and quickly.

        So danger ranks a route rather than disqualifying it, and "no route" now
        means what it says: BuildSim could not find a path at all.

        A clear route is searched for first, over our own copy of the walkable
        graph with the alarming rooms removed. BuildSim only ever offers the
        shortest way to each exit, and when the fire is in a corridor every one
        of those can run through it, however clear the long way round is.
        """
        cached = self._cache.get(space_key)
        if cached is not None and cached[1] == danger:
            return list(cached[0])  # a copy: the caller consumes it
        space = world.spaces.get(space_key)
        if space is None:
            return []
        if self.walkways is not None:
            usable = [
                (level, name)
                for level, names in exits.items()
                for name in names
                if key_of(level, name) not in danger
            ]
            clear = self.walkways.route(space.level, space.name, usable, danger - {space_key})
            if clear:
                self._cache[space_key] = (clear, frozenset(danger))
                return list(clear)
        best: tuple[tuple[int, float], list[dict]] | None = None
        # Every real exit in the building is a candidate, not just the ones on
        # this storey. The stairs are part of the walkable graph, so somebody on
        # the second floor is routed to a door on the ground floor rather than
        # to the top of a staircase.
        for exit_level, exit_name in ((lv, n) for lv, names in exits.items() for n in names):
            if key_of(exit_level, exit_name) in danger:
                continue  # never send people *to* a burning exit; that is a dead end
            try:
                result = await self.client.route(space.name, exit_name, space.level, exit_level)
            except BuildSimError:
                continue  # this exit is unreachable; try the next one
            path = (result or {}).get("path") or []
            if not path:
                continue
            # Fewest burning rooms crossed first, then shortest. A route through
            # one alarming corridor beats one through three, and a clear route
            # beats both however far round it goes.
            rank = (self._hazard(world, space.level, path, danger, space_key), self._cost(path))
            if best is None or rank < best[0]:
                best = (rank, path)
        if best is None:
            self._cache.pop(space_key, None)
            return []
        # Keyed by the danger it was worked out against, so it is recomputed when
        # the fire moves and reused on every tick in between.
        self._cache[space_key] = (best[1], frozenset(danger))
        return list(best[1])

    def _cost(self, path: list[dict]) -> float:
        """How far a route really is, in floor-plan units.

        Walking distance alone under-counts a route that changes storey: the
        stairwell above is at almost the same x, y as the stairwell below, so a
        three-flight descent measures as nearly nothing and would always beat a
        short walk to a door on this floor. Each change of storey therefore
        carries the same fixed cost BuildSim's own router gives a stair edge.
        """
        levels = [node.get("level") for node in path if node.get("level")]
        changes = sum(1 for a, b in zip(levels, levels[1:]) if a != b)
        return path_length(path) + changes * STAIR_COST

    def _hazard(
        self, world: World, level: str, path: list[dict], danger: set[str], origin: str = ""
    ) -> int:
        """How many alarming rooms this route crosses on the way out.

        `origin` is where the walk starts and does not count. Every route out of
        a burning room begins inside one, so counting it would make every route
        look equally bad to the people who most need a good one.
        """
        crossed = set()
        for node in path:
            key = self._space_key(world, level, node)
            if key and key != origin and key in danger:
                crossed.add(key)  # a room is one hazard however many nodes it has
        return len(crossed)

    @staticmethod
    def _space_key(world: World, level: str, node: dict) -> str:
        """A route node names a room only sometimes; "" means "stay put".

        A multi-floor route annotates every node with the storey it is on, and
        that is what a route leaving the floor has to be read by. `level` is the
        fallback for a single-floor answer, which carries no annotation.
        """
        key = key_of(node.get("level") or level, node.get("name") or "")
        return key if key in world.spaces else ""
