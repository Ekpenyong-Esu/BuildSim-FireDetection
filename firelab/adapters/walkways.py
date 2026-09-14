"""Escape routes searched here, over the same walkable graph BuildSim routes on.

BuildSim answers "the shortest way from A to B" and nothing else. It steers
round a burning *room* only because we publish that room's doors as blocked,
and corridors have no doors to block. So when the fire is in a corridor, the
shortest way to every exit can run straight through it, and asking BuildSim
about each exit in turn offers nothing but routes through the fire to pick from.

Here the alarming rooms are simply taken out of the graph before searching. The
graph is joined across storeys as BuildSim's `BuildMultiFloorGraph` joins it,
plus the stairs that land in a corridor, which BuildSim's merge leaves out.
"""

import heapq
from collections import defaultdict
from collections.abc import Iterable

from .world_builder import key_of, level_of

# What one change of storey costs, in floor-plan units. The same figure BuildSim
# gives a stair edge in its own graph, so our ranking agrees with its routing.
STAIR_COST = 20.0

Node = tuple[str, int]  # (level, node id within that floor's graph)


class Walkways:
    """Every floor's walkable graph, joined at the stairs, searchable offline."""

    def __init__(self, floors: dict[str, dict], cross_floor_edges: list[dict]) -> None:
        """Merge the floors BuildSim served us with the stairs that join them."""
        self._nodes: dict[Node, dict] = {}
        self._links: dict[Node, list[tuple[Node, float]]] = defaultdict(list)
        self._ends: dict[tuple[str, str], Node] = {}  # where a route to or from a room starts
        landings: dict[tuple[str, str], Node] = {}  # where a stair meets a floor
        named: dict[tuple[str, str], list[Node]] = defaultdict(list)

        for level, payload in floors.items():
            graph = payload.get("walkable_graph") or {}
            for node in graph.get("nodes", []):
                here = (level, node["id"])
                self._nodes[here] = node
                name, kind = node.get("name"), node.get("type")
                if not name:
                    continue
                named[(level, name)].append(here)
                # As BuildSim resolves a route's endpoints: the room node when
                # there is one, otherwise the first node carrying that name.
                end = self._ends.get((level, name))
                if end is None or (kind == "room" and self._nodes[end].get("type") != "room"):
                    self._ends[(level, name)] = here
                # As BuildSim joins storeys: the entry node, else the room node.
                if kind == "entry" or (kind == "room" and (level, name) not in landings):
                    landings[(level, name)] = here
            for edge in graph.get("edges", []):
                a, b = (level, edge.get("from")), (level, edge.get("to"))
                if a in self._nodes and b in self._nodes:
                    self._link(a, b, float(edge.get("weight") or 0.0) or self._gap(a, b))

        for edge in cross_floor_edges:
            if edge.get("type") == "elevator":
                continue  # nobody takes a lift out of a burning building
            lower = (level_of(str(edge.get("from_level", ""))), str(edge.get("from_name", "")))
            upper = (level_of(str(edge.get("to_level", ""))), str(edge.get("to_name", "")))
            # BuildSim can only land a stair on a room or a doorway, and quietly
            # drops the ones that arrive in a corridor: 8 of this building's 26
            # stairs. They are real stairs, and one of them is the only way
            # round a fire in corridor 1540. So a corridor landing is the
            # corridor node nearest the other end, a stairwell being at much the
            # same x, y on every floor.
            ends_a = [landings[lower]] if lower in landings else named.get(lower, [])
            ends_b = [landings[upper]] if upper in landings else named.get(upper, [])
            if ends_a and ends_b:
                a, b = min(((a, b) for a in ends_a for b in ends_b), key=lambda p: self._gap(*p))
                self._link(a, b, STAIR_COST)

    def route(
        self, level: str, name: str, exits: Iterable[tuple[str, str]], avoid: set[str]
    ) -> list[dict]:
        """The shortest way from a room to whichever exit is nearest, never
        setting foot in a room listed in `avoid` (space keys).

        One search covers every exit at once. [] means every way out crosses
        something in `avoid`, or that the room is not on the graph at all.
        """
        start = self._ends.get((level, name))
        goals = {self._ends[e] for e in exits if e in self._ends}
        if start is None or not goals:
            return []
        best = {start: 0.0}
        came_from: dict[Node, Node] = {}
        queue = [(0.0, start)]
        while queue:
            cost, here = heapq.heappop(queue)
            if cost > best[here]:
                continue  # a stale entry: a cheaper way here was already found
            if here in goals:
                return self._waypoints(came_from, here)
            for there, weight in self._links[here]:
                if self._key(there) in avoid:
                    continue
                if cost + weight < best.get(there, float("inf")):
                    best[there] = cost + weight
                    came_from[there] = here
                    heapq.heappush(queue, (cost + weight, there))
        return []

    def _link(self, a: Node, b: Node, weight: float) -> None:
        """Walkable both ways."""
        self._links[a].append((b, weight))
        self._links[b].append((a, weight))

    def _gap(self, a: Node, b: Node) -> float:
        """Straight-line distance, for an edge that came without a weight."""
        na, nb = self._nodes[a], self._nodes[b]
        return ((na["x"] - nb["x"]) ** 2 + (na["y"] - nb["y"]) ** 2) ** 0.5

    def _key(self, node: Node) -> str:
        """The space a node stands in, "" for an unnamed one."""
        name = self._nodes[node].get("name")
        return key_of(node[0], name) if name else ""

    def _waypoints(self, came_from: dict[Node, Node], last: Node) -> list[dict]:
        """Walk back from the exit, in the node shape BuildSim's router returns."""
        chain = [last]
        while chain[-1] in came_from:
            chain.append(came_from[chain[-1]])
        return [
            {
                "name": self._nodes[node].get("name") or "",
                "level": node[0],
                "x": self._nodes[node]["x"],
                "y": self._nodes[node]["y"],
            }
            for node in reversed(chain)
        ]
