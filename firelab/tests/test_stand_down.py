"""The engine holds a neighbour's stand-down while the fire next door is still lit."""

import unittest

from firelab.app.config import Config
from firelab.app.engine import actuation
from firelab.app.engine.core import Engine
from firelab.domain import agent as agent_mod
from firelab.domain import world as world_mod


def room(key):
    level, name = key.split("/")
    return world_mod.Space(key=key, level=level, name=name, kind="room", area_m2=20.0, center=(0.0, 0.0))


class TestStandDown(unittest.TestCase):
    def setUp(self):
        self.engine = Engine(Config())
        for key in ("level0/FIRE", "level0/NEXT", "level0/FAR"):
            self.engine.world.spaces[key] = room(key)
        self.engine.world.couplings.append(world_mod.Coupling(a="level0/FIRE", b="level0/NEXT", conductance=1.0))
        self.engine.agents["level0/FIRE"] = agent_mod.RoomAgent(space="level0/FIRE", state="CONFIRMED")
        self.engine.agents["level0/NEXT"] = agent_mod.RoomAgent(space="level0/NEXT", state="CLEARING")

    def test_the_neighbour_of_a_burning_room_keeps_its_door_and_water(self):
        for kind, value in (("fire_door", "open"), ("sprinkler", "off")):
            with self.subTest(kind=kind):
                verdict = actuation.apply(self.engine, agent_mod.Command(kind, "level0/NEXT", value, "clearing"))
                self.assertFalse(verdict.allowed)
                self.assertIn("still alarming", verdict.reason)

    def test_a_room_with_no_burning_neighbour_stands_down(self):
        verdict = actuation.apply(self.engine, agent_mod.Command("fire_door", "level0/FAR", "open", "clearing"))
        self.assertTrue(verdict.allowed)

    def test_once_the_neighbour_clears_the_request_goes_through(self):
        self.engine.agents["level0/FIRE"].state = "CLEARING"
        verdict = actuation.apply(self.engine, agent_mod.Command("sprinkler", "level0/NEXT", "off", "clearing"))
        self.assertTrue(verdict.allowed)


if __name__ == "__main__":
    unittest.main()
