"""Joining the storeys: stairwells as couplings, and escapes that leave the floor.

Each floor's walkable graph stops at the slab, so on their own the storeys are
sealed from one another. BuildSim publishes the stairs separately and merges
them into a multi-floor graph; this file checks we use them for both of the
things they are — a way down for people, and a way up for smoke.
"""

import unittest

from firelab.adapters.world_builder import STAIR_CONDUCTANCE, level_of, stair_couplings
from firelab.app.evacuation import STAIR_COST, Evacuation
from firelab.domain import physics
from firelab.domain import world as world_mod
from firelab.domain.occupants import Occupant

# Two storeys, joined at the stairwell, exactly as BuildSim reports them.
EDGES = [
    {"from_level": "abuilding/level0", "from_name": "STAIR",
     "to_level": "abuilding/level1", "to_name": "STAIR", "type": "stair"},
]


def two_storeys() -> world_mod.World:
    world = world_mod.World()
    for level in ("level0", "level1"):
        for index, name in enumerate(("ROOM", "STAIR", "EXIT")):
            key = f"{level}/{name}"
            world.spaces[key] = world_mod.Space(
                key=key, level=level, name=name, kind="room",
                area_m2=25.0, center=(float(index), 0.0),
            )
        world.couplings.append(
            world_mod.Coupling(a=f"{level}/ROOM", b=f"{level}/STAIR", conductance=0.5)
        )
    return world


class TestStairCouplings(unittest.TestCase):
    def test_a_qualified_level_is_reduced_to_ours(self):
        self.assertEqual(level_of("abuilding/level0"), "level0")
        self.assertEqual(level_of("level2"), "level2")

    def test_a_stairwell_becomes_a_coupling(self):
        world = two_storeys()
        stairs = stair_couplings(EDGES, world.spaces)
        self.assertEqual(len(stairs), 1)
        self.assertEqual({stairs[0].a, stairs[0].b}, {"level0/STAIR", "level1/STAIR"})
        self.assertEqual(stairs[0].conductance, STAIR_CONDUCTANCE)

    def test_the_same_stairwell_from_both_ends_is_one_coupling(self):
        reversed_edge = {"from_level": "abuilding/level1", "from_name": "STAIR",
                         "to_level": "abuilding/level0", "to_name": "STAIR"}
        world = two_storeys()
        self.assertEqual(len(stair_couplings([*EDGES, reversed_edge], world.spaces)), 1)

    def test_an_edge_naming_an_unknown_room_is_skipped(self):
        world = two_storeys()
        bogus = {"from_level": "abuilding/level0", "from_name": "NOWHERE",
                 "to_level": "abuilding/level1", "to_name": "STAIR"}
        self.assertEqual(stair_couplings([bogus], world.spaces), [])


class TestSmokeClimbsTheStairs(unittest.TestCase):
    """The point of the coupling: a ground-floor fire is smelled upstairs."""

    def test_sealed_storeys_keep_smoke_downstairs(self):
        world = two_storeys()  # no stairwell coupling
        for _ in range(200):
            physics.step(world, {"level0/ROOM": (500.0, 1.5, 400.0)}, 1.0)
        self.assertEqual(world.spaces["level1/STAIR"].smoke, 0.0)

    def test_a_stairwell_carries_smoke_upward(self):
        world = two_storeys()
        world.couplings.extend(stair_couplings(EDGES, world.spaces))
        for _ in range(200):
            physics.step(world, {"level0/ROOM": (500.0, 1.5, 400.0)}, 1.0)
        self.assertGreater(world.spaces["level1/STAIR"].smoke, 0.0)
        # It thins with every doorway, so upstairs is never worse than the fire.
        self.assertLess(world.spaces["level1/STAIR"].smoke, world.spaces["level0/ROOM"].smoke)


class FakeMultiFloor:
    """BuildSim's multi-floor router: every node annotated with its storey."""

    def __init__(self):
        self.calls = []

    async def route(self, from_name, to_name, from_level, to_level="", graph="walkable"):
        self.calls.append((from_name, from_level, to_name, to_level))
        if to_level == "level0":  # down the stairs and out the ground-floor door
            path = [("ROOM", "level1", 0.0), ("STAIR", "level1", 1.0),
                    ("STAIR", "level0", 1.0), ("EXIT", "level0", 2.0)]
        else:  # the landing on this floor, which is not a way out of the building
            path = [("ROOM", "level1", 0.0), ("EXIT", "level1", 2.0)]
        return {"path": [{"name": n, "level": lv, "x": x, "y": 0.0} for n, lv, x in path]}


class TestEscapingDownstairs(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.world = two_storeys()
        self.world.couplings.extend(stair_couplings(EDGES, self.world.spaces))
        self.client = FakeMultiFloor()
        self.evacuation = Evacuation(self.client)

    async def test_an_upstairs_occupant_is_routed_to_a_ground_floor_door(self):
        # Only the ground floor has a real way out of the building.
        occupant = Occupant(id="o", name="p", space="level1/ROOM", position=[0.0, 0.0])
        await self.evacuation.plan(
            [occupant], self.world, {"level1/ROOM"}, {"level0": ["EXIT"]}
        )
        self.assertEqual(occupant.route_spaces[-1], "level0/EXIT")

    async def test_the_route_is_read_by_each_node_s_own_storey(self):
        # Assuming the starting level would put the ground-floor half upstairs.
        occupant = Occupant(id="o", name="p", space="level1/ROOM", position=[0.0, 0.0])
        await self.evacuation.plan(
            [occupant], self.world, {"level1/ROOM"}, {"level0": ["EXIT"]}
        )
        self.assertEqual(
            occupant.route_spaces,
            ["level1/ROOM", "level1/STAIR", "level0/STAIR", "level0/EXIT"],
        )

    async def test_the_exit_is_asked_for_by_qualified_level(self):
        occupant = Occupant(id="o", name="p", space="level1/ROOM", position=[0.0, 0.0])
        await self.evacuation.plan(
            [occupant], self.world, {"level1/ROOM"}, {"level0": ["EXIT"]}
        )
        self.assertEqual(self.client.calls, [("ROOM", "level1", "EXIT", "level0")])

    async def test_changing_storey_is_not_free(self):
        # Two flights of stairs measure almost nothing in x, y, so without a
        # penalty a needless descent would always beat a walk across the floor.
        downstairs = [{"name": "STAIR", "level": "level1", "x": 1.0, "y": 0.0},
                      {"name": "STAIR", "level": "level0", "x": 1.0, "y": 0.0}]
        same_floor = [{"name": "ROOM", "level": "level1", "x": 0.0, "y": 0.0},
                      {"name": "EXIT", "level": "level1", "x": 5.0, "y": 0.0}]
        self.assertAlmostEqual(self.evacuation._cost(downstairs), STAIR_COST)
        self.assertGreater(self.evacuation._cost(downstairs), self.evacuation._cost(same_floor))


if __name__ == "__main__":
    unittest.main()
