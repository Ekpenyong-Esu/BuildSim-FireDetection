"""Physics is lumped per room; diffusion is the only way smoke leaves the fire room."""

import unittest

from firelab.domain import physics
from firelab.domain import world as world_mod
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


class TestDiffusionConserves(unittest.TestCase):
    """Smoke may move between rooms. It may not appear.

    Each doorway used to move its own share of the gap independently, so a
    corridor with twenty doorways handed out several times what it held. The
    shortfall vanished into the clamp at the end of the step while every
    neighbour kept what it was given, and the building filled with smoke nobody
    produced — 914 rooms "lost" from one office fire at the highest clock speed,
    5 at the lowest, from the same fire over the same simulated minutes.
    """

    @staticmethod
    def _hub(neighbours: int) -> world_mod.World:
        """One room with `neighbours` doorways off it, holding all the smoke."""
        world = world_mod.World()
        for key in ["hub"] + [f"n{i}" for i in range(neighbours)]:
            world.spaces[key] = world_mod.Space(
                key=key, level="level0", name=key, kind="room",
                area_m2=25.0, center=(0.0, 0.0),
            )
        for i in range(neighbours):
            world.couplings.append(
                world_mod.Coupling(a="hub", b=f"n{i}", conductance=1.0)
            )
        world.spaces["hub"].smoke = 1.0
        return world

    def test_no_smoke_is_created_however_many_doorways(self):
        for neighbours in (1, 4, 10, 20, 40):
            for dt in (0.5, 2.5, 10.0):
                with self.subTest(neighbours=neighbours, dt=dt):
                    world = self._hub(neighbours)
                    before = sum(s.smoke for s in world.spaces.values())
                    physics.step(world, {}, dt)
                    after = sum(s.smoke for s in world.spaces.values())
                    self.assertLessEqual(after, before + 1e-9)

    def test_no_room_gives_away_more_than_it_has(self):
        # The clamp at the end of a step hides a negative, so check the value
        # before it would be clamped: the hub must keep a non-negative share.
        world = self._hub(20)
        physics._diffuse(world, 2.5)
        self.assertGreaterEqual(world.spaces["hub"].smoke, 0.0)
        self.assertLessEqual(sum(s.smoke for s in world.spaces.values()), 1.0 + 1e-9)

    def test_smoke_still_reaches_the_neighbours(self):
        # Conserving it must not mean freezing it in place.
        world = self._hub(4)
        physics.step(world, {}, 1.0)
        self.assertGreater(world.spaces["n0"].smoke, 0.0)

    def test_the_answer_does_not_depend_on_the_clock_speed(self):
        # The speed factor changes the step size, and used to change the physics
        # with it: the same fire was survivable paused and catastrophic at x600.
        results = []
        for dt in (0.5, 2.5):
            world = self._hub(20)
            for _ in range(int(60 / dt)):  # one simulated minute either way
                physics.step(world, {}, dt)
            results.append(sum(s.smoke for s in world.spaces.values()))
        self.assertAlmostEqual(results[0], results[1], places=6)
