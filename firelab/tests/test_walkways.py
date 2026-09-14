"""Finding the way round a burning corridor, which BuildSim's router cannot.

BuildSim steers round a burning room by its blocked doors, and a corridor has
none. Every shortest route out of the wing below runs through CORRIDOR, so the
only safe answer is the long way round, and it has to be searched for.

    ROOM ── CORRIDOR ── EXIT          the short way, through the fire
      └──── BACKWAY ─── STAIR ┐
                              │ (stairs)
    level1:  UPPER ─── STAIR ─┘ ... and back down to EXIT on level0
"""

import unittest

from firelab.adapters.walkways import Walkways
from firelab.app.evacuation import Evacuation
from firelab.domain import world as world_mod
from firelab.domain.occupants import Occupant

from .test_evacuation import FakeBuildSim


def node(id, name, kind, x, y=0.0):
    return {"id": id, "name": name, "type": kind, "x": x, "y": y}


def edge(a, b, weight):
    return {"from": a, "to": b, "weight": weight}


FLOORS = {
    "level0": {
        "walkable_graph": {
            "nodes": [
                node(0, "ROOM", "room", 0.0),
                node(1, "ROOM", "entry", 1.0),
                node(2, "CORRIDOR", "corridor", 2.0),
                node(3, "CORRIDOR", "corridor", 3.0),
                node(4, "EXIT", "entry", 4.0),
                node(5, "EXIT", "room", 5.0),
                node(6, "BACKWAY", "corridor", 1.0, 5.0),
                node(7, "STAIR", "entry", 1.0, 9.0),
            ],
            "edges": [
                edge(0, 1, 1), edge(1, 2, 1), edge(2, 3, 1), edge(3, 4, 1), edge(4, 5, 1),
                edge(1, 6, 5), edge(6, 7, 5),
            ],
        }
    },
}

LONG_WAY = {
    **FLOORS,
    "level1": {
        "walkable_graph": {
            "nodes": [node(0, "STAIR", "entry", 1.0, 9.0), node(1, "EXIT", "room", 5.0)],
            "edges": [edge(0, 1, 30)],
        }
    },
}
STAIRS = [{"from_level": "abuilding/level0", "from_name": "STAIR",
           "to_level": "abuilding/level1", "to_name": "STAIR", "type": "stair"}]
EXITS = [("level0", "EXIT")]


def names(path):
    """Collapse consecutive nodes of one room: the rooms walked through, in order."""
    out = []
    for n in path:
        if not out or out[-1] != (n["level"], n["name"]):
            out.append((n["level"], n["name"]))
    return [f"{level}/{name}" for level, name in out]


class TestWalkways(unittest.TestCase):
    def test_without_fire_it_is_the_shortest_way(self):
        path = Walkways(FLOORS, []).route("level0", "ROOM", EXITS, set())
        self.assertEqual(names(path), ["level0/ROOM", "level0/CORRIDOR", "level0/EXIT"])

    def test_it_starts_and_ends_where_buildsim_would(self):
        # BuildSim resolves a room name to its room node, not its doorway.
        path = Walkways(FLOORS, []).route("level0", "ROOM", EXITS, set())
        self.assertEqual((path[0]["x"], path[-1]["x"]), (0.0, 5.0))

    def test_a_burning_corridor_is_walked_round(self):
        # Down the stairs is not possible here; up and back down is the only way.
        floors = {
            "level0": FLOORS["level0"],
            "level1": {"walkable_graph": {
                "nodes": [node(0, "STAIR", "entry", 1.0, 9.0), node(1, "STAIR2", "entry", 4.0, 9.0)],
                "edges": [edge(0, 1, 3)],
            }},
        }
        floors["level0"] = {"walkable_graph": {
            "nodes": [*FLOORS["level0"]["walkable_graph"]["nodes"], node(8, "STAIR2", "entry", 4.0, 9.0)],
            "edges": [*FLOORS["level0"]["walkable_graph"]["edges"], edge(8, 4, 5)],
        }}
        stairs = [*STAIRS, {"from_level": "abuilding/level0", "from_name": "STAIR2",
                            "to_level": "abuilding/level1", "to_name": "STAIR2", "type": "stair"}]
        path = Walkways(floors, stairs).route("level0", "ROOM", EXITS, {"level0/CORRIDOR"})
        self.assertNotIn("level0/CORRIDOR", names(path))
        self.assertEqual(names(path)[-1], "level0/EXIT")
        # Each node says which storey it is on, so the viewer draws it there.
        self.assertIn("level1", {n["level"] for n in path})

    def test_no_clear_way_is_an_empty_answer_not_a_route_through_fire(self):
        path = Walkways(FLOORS, []).route("level0", "ROOM", EXITS, {"level0/CORRIDOR"})
        self.assertEqual(path, [])

    def test_the_nearest_exit_is_chosen_from_several(self):
        path = Walkways(LONG_WAY, STAIRS).route(
            "level0", "ROOM", [("level1", "EXIT"), ("level0", "EXIT")], set()
        )
        self.assertEqual(names(path)[-1], "level0/EXIT")

    def test_the_stairs_join_the_storeys(self):
        path = Walkways(LONG_WAY, STAIRS).route("level0", "ROOM", [("level1", "EXIT")], set())
        self.assertEqual(names(path)[-2:], ["level1/STAIR", "level1/EXIT"])

    def test_without_the_stairs_the_storeys_are_sealed(self):
        path = Walkways(LONG_WAY, []).route("level0", "ROOM", [("level1", "EXIT")], set())
        self.assertEqual(path, [])

    def test_a_stair_landing_in_a_corridor_is_still_a_stair(self):
        # BuildSim's own merge drops these; the corridor node nearest the other
        # end of the stair is where it lands.
        floors = {
            "level0": FLOORS["level0"],
            "level1": {"walkable_graph": {
                "nodes": [node(0, "LANDING", "corridor", 9.0, 9.0),
                          node(1, "LANDING", "corridor", 1.0, 9.0),
                          node(2, "EXIT", "room", 5.0)],
                "edges": [edge(0, 1, 8), edge(1, 2, 30)],
            }},
        }
        stairs = [{**STAIRS[0], "to_name": "LANDING"}]
        path = Walkways(floors, stairs).route("level0", "ROOM", [("level1", "EXIT")], set())
        self.assertEqual(names(path)[-2:], ["level1/LANDING", "level1/EXIT"])
        landing = [n for n in path if n["name"] == "LANDING"]
        self.assertEqual([(n["x"], n["y"]) for n in landing], [(1.0, 9.0)])

    def test_a_lift_is_never_part_of_an_escape(self):
        lift = [{**STAIRS[0], "type": "elevator"}]
        path = Walkways(LONG_WAY, lift).route("level0", "ROOM", [("level1", "EXIT")], set())
        self.assertEqual(path, [])


class TestEvacuationPrefersTheClearWay(unittest.IsolatedAsyncioTestCase):
    """The bug as it was seen: every route BuildSim offered crossed the fire."""

    def setUp(self):
        floors = {
            "level0": {"walkable_graph": {
                "nodes": [
                    node(0, "ROOM", "room", 0.0), node(1, "CORRIDOR", "corridor", 1.0),
                    node(2, "EXIT", "room", 2.0), node(3, "BACKWAY", "corridor", 0.0, 5.0),
                ],
                "edges": [edge(0, 1, 1), edge(1, 2, 1), edge(0, 3, 5), edge(3, 2, 5)],
            }},
        }
        self.world = world_mod.World()
        for index, name in enumerate(("ROOM", "CORRIDOR", "EXIT", "BACKWAY")):
            key = f"level0/{name}"
            self.world.spaces[key] = world_mod.Space(
                key=key, level="level0", name=name, kind="corridor",
                area_m2=25.0, center=(float(index), 0.0),
            )
        # BuildSim only knows the short way, through the corridor.
        self.client = FakeBuildSim({("ROOM", "EXIT"): [("ROOM", 0.0), ("CORRIDOR", 1.0), ("EXIT", 2.0)]})
        self.evacuation = Evacuation(self.client)
        self.evacuation.walkways = Walkways(floors, [])
        self.exits = {"level0": ["EXIT"]}

    def occupant(self):
        return Occupant(id="o", name="p", space="level0/ROOM", position=[0.0, 0.0])

    async def test_a_burning_corridor_is_walked_round(self):
        occupant = self.occupant()
        await self.evacuation.plan(
            [occupant], self.world, {"level0/ROOM", "level0/CORRIDOR"}, self.exits
        )
        self.assertNotIn("level0/CORRIDOR", occupant.route_spaces)
        self.assertEqual(occupant.route_spaces[-1], "level0/EXIT")
        self.assertEqual(self.client.calls, [], "BuildSim asked although a clear way was known")

    async def test_walled_in_still_falls_back_to_the_least_bad_way(self):
        occupant = self.occupant()
        danger = {"level0/ROOM", "level0/CORRIDOR", "level0/BACKWAY"}
        await self.evacuation.plan([occupant], self.world, danger, self.exits)
        self.assertEqual(occupant.status, "evacuating")
        self.assertIn("level0/CORRIDOR", occupant.route_spaces)

    async def test_a_walker_heading_into_the_fire_is_turned_round(self):
        occupant = self.occupant()
        await self.evacuation.plan([occupant], self.world, {"level0/ROOM"}, self.exits)
        self.assertIn("level0/CORRIDOR", occupant.route_spaces)
        await self.evacuation.plan(
            [occupant], self.world, {"level0/ROOM", "level0/CORRIDOR"}, self.exits
        )
        self.assertNotIn("level0/CORRIDOR", occupant.route_spaces)


if __name__ == "__main__":
    unittest.main()
