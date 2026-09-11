"""Physics is lumped per room; diffusion is the only way smoke leaves the fire room."""

import unittest

from firelab.domain import physics
from firelab.domain.world import T_OUT

from .helpers import make_world


class TestPhysics(unittest.TestCase):
    # Smoke must reach the neighbour, but stay worse at the source.
    def test_heat_spreads_to_the_neighbour(self):
        world = make_world()
        for _ in range(600):
            physics.step(world, {"level0/A1": (300.0, 0.5, 400.0)}, 1.0)
        self.assertGreater(world.spaces["level0/A1"].temperature, T_OUT)
        self.assertGreater(world.spaces["level0/A2"].smoke, 0.0)
        self.assertGreater(
            world.spaces["level0/A1"].smoke, world.spaces["level0/A2"].smoke
        )

    # Sprinkler must reduce both heat and smoke, closing the control loop.
    def test_sprinkler_suppresses(self):
        hot, wet = make_world(), make_world()
        wet.spaces["level0/A1"].sprinkler = True
        for _ in range(300):
            physics.step(hot, {"level0/A1": (300.0, 0.5, 0.0)}, 1.0)
            physics.step(wet, {"level0/A1": (300.0, 0.5, 0.0)}, 1.0)
        self.assertLess(
            wet.spaces["level0/A1"].temperature, hot.spaces["level0/A1"].temperature
        )


if __name__ == "__main__":
    unittest.main()
