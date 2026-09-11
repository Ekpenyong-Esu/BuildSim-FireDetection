"""Evacuation: ask BuildSim for escape routes and walk people along them.

The only reason this is not in `domain/` is the route lookup, which is a
network call. Everything else here delegates to `domain.occupants`.
"""

from ..adapters.buildsim import BuildSim, BuildSimError
from ..adapters.publisher import path_length
from ..adapters.world_builder import key_of
from ..domain import occupants as occupants_mod
from ..domain.world import World


class Evacuation:
    """Works out where people should go, and moves them there tick by tick."""

    def __init__(self, client: BuildSim) -> None:
        self.client = client
        self.display_route: list[dict] = []  # the one route drawn in the viewer
        self.display_level = ""  # which storey that route is on
        # Everyone leaving the same room takes the same way out, so the answer
        # is cached instead of asking BuildSim once per person.
        self._cache: dict[str, list[dict]] = {}

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
        """Give every threatened occupant without a route a path to an exit."""
        if not danger:
            return
        for occupant in people:
            # The fire moves after routes are handed out. Anyone whose remaining
            # path now runs through a burning room is sent back for a new one.
            # The room they are standing in is not "ahead": it is usually the one
            # alight, and leaving it is the whole point.
            ahead = [key for key in occupant.route_spaces if key != occupant.space]
            if occupant.route and any(key in danger for key in ahead):
                occupant.route = []
                occupant.route_spaces = []
            if occupant.safe or occupant.route:
                continue  # already out, or already walking
            # Once someone starts evacuating they keep going, even if their room
            # is later declared safe.
            if occupant.status != "evacuating" and occupant.space not in danger:
                continue
            occupant.status = "evacuating"
            path = await self._path(occupant.space, world, danger, exits)
            if not path:
                occupant.status = "no route"  # trapped: this counts against the run
                continue
            level = occupant.space.split("/")[0]
            # Two parallel lists: where to walk, and which room that point is in.
            occupant.route = [[node["x"], node["y"]] for node in path]
            occupant.route_spaces = [self._space_key(world, level, node) for node in path]

        self._choose_display_route(danger)

    def _choose_display_route(self, danger: set[str]) -> None:
        """Pick the one route the viewer draws: the way out of a burning room.

        Taking whichever route was worked out last drew whoever happened to be
        planned last, which in a three-storey building was usually somebody two
        floors from the fire. Sorting makes the choice the same on every tick,
        so the line does not flicker between everyone leaving the same room.
        """
        for key in sorted(danger):
            path = self._cache.get(key)
            if path:
                self.display_route = path
                self.display_level = key.split("/")[0]
                return

    def advance(self, people: list[occupants_mod.Occupant], distance: float) -> None:
        """Move everyone who is evacuating `distance` further along their route."""
        for occupant in people:
            if occupant.status != "evacuating" or occupant.safe or not occupant.route:
                continue
            occupants_mod.advance(occupant, distance * occupant.speed)

    async def _path(
        self, space_key: str, world: World, danger: set[str], exits: dict[str, list[str]]
    ) -> list[dict]:
        """The shortest safe way out. Sending everyone to the first listed exit
        piles the whole building into one room."""
        cached = self._cache.get(space_key)
        if cached is not None:
            if not self._through_fire(world, space_key.split("/")[0], cached, danger, space_key):
                return list(cached)  # a copy: the caller consumes it
            del self._cache[space_key]  # the fire has spread onto the way out
        space = world.spaces.get(space_key)
        if space is None:
            return []
        best: list[dict] = []
        for exit_name in exits.get(space.level, []):
            if key_of(space.level, exit_name) in danger:
                continue  # never send people towards a burning exit
            try:
                result = await self.client.route(space.name, exit_name, space.level)
            except BuildSimError:
                continue  # this exit is unreachable; try the next one
            path = (result or {}).get("path") or []
            if self._through_fire(world, space.level, path, danger, space_key):
                continue  # never route people *through* a burning room either
            if path and (not best or path_length(path) < path_length(best)):
                best = path
        if best:
            self._cache[space_key] = best
        return list(best)

    def _through_fire(
        self, world: World, level: str, path: list[dict], danger: set[str], origin: str = ""
    ) -> bool:
        """Does this route pass through an alarming room on the way out?

        `origin` is where the walk starts, and it does not count. Every route out
        of a burning room begins inside one, so counting it would reject every
        path the people who most need one could ever be given.
        """
        for node in path:
            key = self._space_key(world, level, node)
            if key != origin and key in danger:
                return True
        return False

    @staticmethod
    def _space_key(world: World, level: str, node: dict) -> str:
        """A route node names a room only sometimes; "" means "stay put"."""
        key = key_of(level, node.get("name") or "")
        return key if key in world.spaces else ""
