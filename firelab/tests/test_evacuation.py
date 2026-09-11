"""Routing people out: the one changed module the preset runs never exercise.

`test_presets.py` deliberately asks nobody to walk anywhere, so everything here
is uncovered by it. BuildSim is faked: these are questions about which path is
chosen and when a path is thrown away, not about HTTP.

The rule the whole file turns on is that the room somebody is standing in is not
an obstacle between them and the door. It is normally the room that is alight,
which is exactly why they are being routed at all.
"""

import unittest

from firelab.adapters.buildsim import BuildSimError
from firelab.adapters.publisher import route as publisher_route
from firelab.app.evacuation import Evacuation
from firelab.domain import world as world_mod
from firelab.domain.occupants import Occupant

LEVEL = "level0"
EXITS = {LEVEL: ["EXIT", "BACK"]}


def key(name: str) -> str:
    return f"{LEVEL}/{name}"


def make_world(*names: str) -> world_mod.World:
    """A flat building of named rooms. Couplings do not matter for routing."""
    world = world_mod.World()
    for index, name in enumerate(names):
        world.spaces[key(name)] = world_mod.Space(
            key=key(name),
            level=LEVEL,
            name=name,
            kind="room",
            area_m2=25.0,
            center=(float(index), 0.0),
        )
    return world


class FakeBuildSim:
    """The route endpoint, and nothing else. Records what it was asked.

    A path is given as (room, distance) pairs rather than bare names, because
    which way out gets chosen depends on how long each one is and a test that
    hides that behind the number of rooms is a test about the wrong thing.
    """

    def __init__(self, paths: dict[tuple[str, str], list[tuple[str, float]]]) -> None:
        self.paths = paths
        self.calls: list[tuple[str, str]] = []

    async def route(self, from_name, to_name, level, graph="walkable"):
        self.calls.append((from_name, to_name))
        nodes = self.paths.get((from_name, to_name))
        if nodes is None:
            raise BuildSimError("no such route")
        # A route starts in the room you are in, so nodes[0] is the origin.
        return {"path": [{"name": name, "x": x, "y": 0.0} for name, x in nodes]}


def person(space: str, **overrides) -> Occupant:
    occupant = Occupant(id="o1", name="Person 1", space=key(space), position=[0.0, 0.0])
    for name, value in overrides.items():
        setattr(occupant, name, value)
    return occupant


class TestLeavingTheBurningRoom(unittest.IsolatedAsyncioTestCase):
    """The case that matters: the person standing in the fire."""

    def setUp(self):
        self.world = make_world("A1", "HALL", "EXIT")
        self.client = FakeBuildSim(
            {("A1", "EXIT"): [("A1", 0.0), ("HALL", 1.0), ("EXIT", 2.0)]}
        )
        self.evacuation = Evacuation(self.client)

    async def test_a_person_in_the_burning_room_is_given_a_way_out(self):
        # Their own room is the only one alight and the corridor beyond is clear.
        occupant = person("A1")
        await self.evacuation.plan([occupant], self.world, {key("A1")}, EXITS)
        self.assertEqual(occupant.status, "evacuating")
        self.assertEqual(occupant.route_spaces, [key("A1"), key("HALL"), key("EXIT")])

    async def test_a_good_route_survives_the_next_tick(self):
        # Planning runs every tick. A route must not be discarded merely because
        # it starts where the person already is.
        occupant = person("A1")
        await self.evacuation.plan([occupant], self.world, {key("A1")}, EXITS)
        planned = list(occupant.route_spaces)
        for _ in range(3):
            await self.evacuation.plan([occupant], self.world, {key("A1")}, EXITS)
        self.assertEqual(occupant.route_spaces, planned)
        self.assertEqual(occupant.status, "evacuating")

    async def test_nobody_is_called_trapped_while_a_clear_path_exists(self):
        occupant = person("A1")
        await self.evacuation.plan([occupant], self.world, {key("A1")}, EXITS)
        self.assertNotEqual(occupant.status, "no route")


class TestRoutingAroundFire(unittest.IsolatedAsyncioTestCase):
    """Fire anywhere ahead of somebody is still an obstacle."""

    def setUp(self):
        # Two ways out of A1: the short one through HALL, a long one to BACK.
        self.world = make_world("A1", "HALL", "EXIT", "BACK")
        self.client = FakeBuildSim(
            {
                ("A1", "EXIT"): [("A1", 0.0), ("HALL", 1.0), ("EXIT", 2.0)],
                ("A1", "BACK"): [("A1", 0.0), ("BACK", 9.0)],  # the long way round
            }
        )
        self.evacuation = Evacuation(self.client)

    async def test_a_burning_room_ahead_is_avoided(self):
        # HALL is alight, so the way out is the back door even though it is
        # a different exit from the one listed first.
        occupant = person("A1")
        await self.evacuation.plan(
            [occupant], self.world, {key("A1"), key("HALL")}, EXITS
        )
        self.assertNotIn(key("HALL"), occupant.route_spaces)
        self.assertEqual(occupant.route_spaces[-1], key("BACK"))

    async def test_no_safe_path_means_trapped(self):
        # Both ways out are alight: this must count against the run rather than
        # quietly sending somebody through the fire.
        occupant = person("A1")
        await self.evacuation.plan(
            [occupant], self.world, {key("A1"), key("HALL"), key("BACK")}, EXITS
        )
        self.assertEqual(occupant.status, "no route")
        self.assertEqual(occupant.route, [])


class TestTheFireSpreading(unittest.IsolatedAsyncioTestCase):
    """A route handed out before the fire moved must not keep being handed out."""

    def setUp(self):
        self.world = make_world("A1", "HALL", "EXIT", "BACK")
        self.client = FakeBuildSim(
            {
                ("A1", "EXIT"): [("A1", 0.0), ("HALL", 1.0), ("EXIT", 2.0)],
                ("A1", "BACK"): [("A1", 0.0), ("BACK", 9.0)],  # the long way round
            }
        )
        self.evacuation = Evacuation(self.client)

    async def test_the_cache_is_dropped_when_fire_reaches_the_route(self):
        first = await self.evacuation._path(key("A1"), self.world, {key("A1")}, EXITS)
        self.assertEqual([n["name"] for n in first], ["A1", "HALL", "EXIT"])
        # HALL catches fire. The cached answer is now wrong and must be replaced.
        second = await self.evacuation._path(
            key("A1"), self.world, {key("A1"), key("HALL")}, EXITS
        )
        self.assertNotIn("HALL", [n["name"] for n in second])

    async def test_an_unchanged_route_is_served_from_the_cache(self):
        # Asking BuildSim once per person per tick would be the slow way to do it.
        await self.evacuation._path(key("A1"), self.world, {key("A1")}, EXITS)
        calls = len(self.client.calls)
        await self.evacuation._path(key("A1"), self.world, {key("A1")}, EXITS)
        self.assertEqual(len(self.client.calls), calls)

    async def test_a_walker_is_re_routed_when_fire_lands_ahead_of_them(self):
        occupant = person("A1")
        await self.evacuation.plan([occupant], self.world, {key("A1")}, EXITS)
        self.assertIn(key("HALL"), occupant.route_spaces)
        await self.evacuation.plan(
            [occupant], self.world, {key("A1"), key("HALL")}, EXITS
        )
        self.assertNotIn(key("HALL"), occupant.route_spaces)


class TestWhoGetsRouted(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.world = make_world("A1", "HALL", "EXIT")
        self.client = FakeBuildSim(
            {
                ("A1", "EXIT"): [("A1", 0.0), ("HALL", 1.0), ("EXIT", 2.0)],
                ("HALL", "EXIT"): [("HALL", 1.0), ("EXIT", 2.0)],
            }
        )
        self.evacuation = Evacuation(self.client)

    async def test_a_quiet_building_routes_nobody(self):
        occupant = person("A1")
        await self.evacuation.plan([occupant], self.world, set(), EXITS)
        self.assertEqual(occupant.status, "idle")
        self.assertEqual(self.client.calls, [])

    async def test_somebody_in_a_safe_room_stays_put(self):
        occupant = person("HALL")
        await self.evacuation.plan([occupant], self.world, {key("A1")}, EXITS)
        self.assertEqual(occupant.status, "idle")

    async def test_somebody_already_walking_keeps_going_once_their_room_is_clear(self):
        # Standing down mid-escape is how people get caught by a re-ignition.
        occupant = person("HALL", status="evacuating")
        await self.evacuation.plan([occupant], self.world, {key("A1")}, EXITS)
        self.assertEqual(occupant.status, "evacuating")
        self.assertEqual(occupant.route_spaces, [key("HALL"), key("EXIT")])

    async def test_people_who_are_out_are_left_alone(self):
        occupant = person("A1", safe=True)
        await self.evacuation.plan([occupant], self.world, {key("A1")}, EXITS)
        self.assertEqual(self.client.calls, [])


if __name__ == "__main__":
    unittest.main()


class TestTheRouteTheViewerDraws(unittest.IsolatedAsyncioTestCase):
    """Only one route is drawn, so it had better be the one at the fire.

    The building has three storeys and the whole building walks out when any
    room confirms, so most people being routed are nowhere near the fire.
    """

    def setUp(self):
        self.world = world_mod.World()
        for level in ("level0", "level1", "level2"):
            for index, name in enumerate(("ROOM", "STAIR", "EXIT")):
                self.world.spaces[f"{level}/{name}"] = world_mod.Space(
                    key=f"{level}/{name}",
                    level=level,
                    name=name,
                    kind="room",
                    area_m2=25.0,
                    center=(float(index), 0.0),
                )
        self.evacuation = Evacuation(
            FakeBuildSim(
                {
                    ("ROOM", "EXIT"): [("ROOM", 0.0), ("STAIR", 1.0), ("EXIT", 2.0)],
                }
            )
        )
        self.exits = {level: ["EXIT"] for level in ("level0", "level1", "level2")}
        # Everyone is walking, but only the ground floor is alight.
        self.people = [
            Occupant(id=f"o-{level}", name=level, space=f"{level}/ROOM",
                     position=[0.0, 0.0], status="evacuating")
            for level in ("level0", "level1", "level2")
        ]

    async def test_the_drawn_route_is_the_one_out_of_the_fire(self):
        await self.evacuation.plan(self.people, self.world, {"level0/ROOM"}, self.exits)
        self.assertEqual(self.evacuation.display_level, "level0")

    async def test_it_is_not_simply_whoever_was_planned_last(self):
        # The level2 occupant is planned last and used to win by default.
        await self.evacuation.plan(self.people, self.world, {"level0/ROOM"}, self.exits)
        self.assertNotEqual(self.evacuation.display_level, "level2")

    async def test_the_choice_is_the_same_on_every_tick(self):
        # Publishing compares against the last route sent; a route that changed
        # every tick would re-frame the viewer's camera four times a second.
        seen = set()
        for _ in range(5):
            await self.evacuation.plan(self.people, self.world, {"level0/ROOM"}, self.exits)
            seen.add(self.evacuation.display_level)
        self.assertEqual(seen, {"level0"})

    async def test_a_fire_upstairs_draws_the_route_upstairs(self):
        await self.evacuation.plan(self.people, self.world, {"level2/ROOM"}, self.exits)
        self.assertEqual(self.evacuation.display_level, "level2")

    async def test_the_published_route_names_its_storey(self):
        # Without this the viewer guesses the floor from the first room name and
        # falls back to level1, drawing a ground-floor escape two storeys up.
        await self.evacuation.plan(self.people, self.world, {"level0/ROOM"}, self.exits)
        payload = publisher_route(
            self.evacuation.display_route, self.evacuation.display_level
        )
        self.assertTrue(all(node["level"] == "level0" for node in payload["path"]))
        self.assertEqual(payload["distance"], 1.0)  # 2 units at 0.5 m each

    async def test_a_route_with_no_known_storey_is_left_alone(self):
        payload = publisher_route([{"name": "ROOM", "x": 0.0, "y": 0.0}])
        self.assertNotIn("level", payload["path"][0])
