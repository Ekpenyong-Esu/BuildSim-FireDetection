"""What pressing Reset actually clears, and what it deliberately keeps.

Reset is not reload: the floor plans and the sensors you installed survive, and
so do your settings, because the Settings panel promises they will. Everything
the *run* produced must not.

The two cases that used to leak are the interesting ones. A sensor broken by a
preset stayed broken, and a fire door closed during the run went on throttling
smoke in the next one — both invisible in the UI, and both quietly wrong in
every number a second run produced.
"""

import unittest

from firelab.app.engine import actuation, scenario, session, truth
from firelab.app.engine.state import EngineState
from firelab.domain import sensing
from firelab.domain.world import T_OUT

from .helpers import make_world

ROOM = "level0/A1"


def dirty_engine() -> EngineState:
    """An engine that has had a real run: a fire, a fault, and a closed door."""
    engine = EngineState()
    engine.world = make_world()
    engine.loaded = True
    engine.now = 8 * 3600.0
    scenario.apply_preset(engine, "drifting-sensor", ROOM)  # injects a fault
    scenario.ignite(engine, ROOM, "flaming", "fast", 0.0, 2000.0)
    for _ in range(600):
        engine.now += 0.5
        truth.advance(engine, 0.5)
        truth.sense(engine, 0.5)
    # Shut a fire door. The room is empty, so the interlocks allow it.
    engine.occupants = []
    actuation.override(engine, "fire_door", ROOM, "closed")
    return engine


class TestResetClearsTheRun(unittest.TestCase):
    def setUp(self):
        self.engine = dirty_engine()

    def test_a_broken_sensor_is_mended(self):
        self.assertTrue(any(d.fault != "none" for d in self.engine.devices.values()))
        session.reset(self.engine)
        self.assertTrue(all(d.fault == "none" for d in self.engine.devices.values()))

    def test_a_closed_door_is_opened_again(self):
        self.assertTrue(any(c.openness < 1.0 for c in self.engine.world.couplings))
        session.reset(self.engine)
        self.assertTrue(all(c.openness == 1.0 for c in self.engine.world.couplings))

    def test_the_building_goes_cold_and_clear(self):
        space = self.engine.world.spaces[ROOM]
        self.assertGreater(space.smoke, 0.0)
        session.reset(self.engine)
        self.assertEqual(space.temperature, T_OUT)
        self.assertEqual(space.smoke, 0.0)
        self.assertEqual(space.co, 0.0)
        self.assertFalse(space.sprinkler)

    def test_everything_the_run_produced_is_gone(self):
        session.reset(self.engine)
        engine = self.engine
        self.assertEqual(engine.sources, [])
        self.assertEqual(engine.probabilities, {})
        self.assertEqual(engine.features, {})
        self.assertEqual(engine.doors, {})
        self.assertEqual(engine.blocks, {})
        self.assertEqual(engine.history.tracks, {})
        self.assertEqual(engine.score.summary()["detections"], 0)
        self.assertTrue(all(not w.series for w in engine.windows.values()))
        self.assertTrue(all(a.state == "NORMAL" for a in engine.agents.values()))
        self.assertTrue(all(not a.pending for a in engine.agents.values()))

    def test_a_reset_device_reads_like_a_new_one(self):
        session.reset(self.engine)
        for device in self.engine.devices.values():
            fresh = sensing.Device.create(device.id, device.space, device.modality)
            self.assertEqual(device.internal, fresh.internal)
            self.assertIsNone(device.reading)
            self.assertEqual(device.drift, 0.0)
            self.assertEqual(device.history, [])


class TestResetKeepsWhatItPromises(unittest.TestCase):
    """The other half of the contract: reset is not reload."""

    def setUp(self):
        self.engine = dirty_engine()

    def test_the_sensors_you_installed_stay_installed(self):
        before = set(self.engine.devices)
        self.assertTrue(before)
        session.reset(self.engine)
        self.assertEqual(set(self.engine.devices), before)

    def test_the_building_stays_loaded(self):
        before = set(self.engine.world.spaces)
        session.reset(self.engine)
        self.assertEqual(set(self.engine.world.spaces), before)
        self.assertTrue(self.engine.loaded)

    def test_your_settings_survive(self):
        # The Settings panel tells the user a change "only matters from the next
        # reset", so a reset that discarded it would break that promise.
        self.engine.config.response.confirm = 0.99
        self.engine.config.seed = 42
        session.reset(self.engine)
        self.assertEqual(self.engine.config.response.confirm, 0.99)
        self.assertEqual(self.engine.config.seed, 42)

    def test_the_building_is_repopulated(self):
        session.reset(self.engine)
        self.assertTrue(self.engine.occupants)
        self.assertTrue(all(not o.safe for o in self.engine.occupants))
        self.assertTrue(all(o.status == "idle" for o in self.engine.occupants))


if __name__ == "__main__":
    unittest.main()
