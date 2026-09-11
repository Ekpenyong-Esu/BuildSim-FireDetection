"""One run per preset, end to end: physics -> sensors -> detector -> agent -> actuators.

The other test files check mechanisms in isolation. These check outcomes, which
is the level every bug that has ever mattered here lived at: each preset makes a
promise in its description, and this file is where that promise is kept.

BuildSim is never contacted. Only the evacuation router needs the network, and
nothing below asks anyone to walk anywhere.
"""

import unittest

from firelab.app.engine import actuation, intelligence, scenario, truth
from firelab.app.engine.state import EngineState

from .helpers import make_world

ROOM = "level0/A1"


class Run:
    """The outcome of one preset: what happened, not how it happened."""

    def __init__(self, preset_id: str, seconds: float = 900.0, dt: float = 0.5) -> None:
        engine = EngineState()
        engine.world = make_world()
        engine.loaded = True
        scenario.apply_preset(engine, preset_id, ROOM)
        self.states = {engine.agents[ROOM].state}
        self.peak = 0.0
        for _ in range(int(seconds / dt)):
            engine.now += dt
            truth.advance(engine, dt)
            truth.sense(engine, dt)
            for command in intelligence.think(engine):
                actuation.apply(engine, command)
            self.states.add(engine.agents[ROOM].state)
            self.peak = max(self.peak, engine.probabilities.get(ROOM, 0.0))
        self.engine = engine
        self.agent = engine.agents[ROOM]
        self.space = engine.world.spaces[ROOM]
        self.score = engine.score.summary()

    def alarmed(self) -> bool:
        """Did the room ever raise a real alarm, however briefly?"""
        return bool(self.states & {"CONFIRMED", "SUPPRESSED"})


# Running a preset takes about a tenth of a second, so each one runs once.
RUNS: dict[str, Run] = {}


def run(preset_id: str) -> Run:
    return RUNS.setdefault(preset_id, Run(preset_id))


class TestRealFires(unittest.TestCase):
    # "Fast flaming fire. The easy case - everything corroborates."
    def test_a_flaming_fire_is_caught_quickly(self):
        result = run("office-fire")
        self.assertTrue(result.alarmed())
        self.assertEqual(result.score["detections"], 1)
        self.assertEqual(result.score["misses"], 0)
        self.assertEqual(result.score["false_alarms"], 0)
        self.assertLess(result.score["worst_latency"], 300.0)
        self.assertTrue(result.space.sprinkler)

    # "Barely any heat, dense smoke, high CO. Only CO catches it."
    def test_a_smoulder_is_caught_without_heat(self):
        result = run("overnight-smoulder")
        self.assertTrue(result.alarmed())
        self.assertEqual(result.score["detections"], 1)
        self.assertEqual(result.score["false_alarms"], 0)
        self.assertLess(result.space.temperature, 35.0)  # below the sprinkler interlock

    # The interlock refuses water in a cold room, and that refusal is a delay and
    # not a cancellation: the request is still outstanding at the end of the run.
    def test_a_refused_sprinkler_is_still_being_asked_for(self):
        result = run("overnight-smoulder")
        self.assertFalse(result.space.sprinkler)
        self.assertIn("sprinkler", [c.kind for c in result.agent.pending])


class TestNuisances(unittest.TestCase):
    # "The classic nuisance. Any alarm here is a false alarm."
    def test_cooking_never_raises_the_alarm(self):
        result = run("kitchen-cooking")
        self.assertFalse(result.alarmed())
        self.assertEqual(result.score["false_alarms"], 0)

    # "Smoke without fire: no heat, no CO."
    def test_dust_never_raises_the_alarm(self):
        result = run("dust-storm")
        self.assertFalse(result.alarmed())
        self.assertEqual(result.score["false_alarms"], 0)

    # "Nothing is burning; one detector drifts upwards. Does it alarm?" It must not.
    def test_a_drifting_sensor_never_raises_the_alarm(self):
        result = run("drifting-sensor")
        self.assertFalse(result.alarmed())
        self.assertEqual(result.score["false_alarms"], 0)


class TestDegradedHardware(unittest.TestCase):
    # "Flaming fire while the smoke detector is dead - CO and heat must carry it."
    # With no absolute CO term in the detector this is impossible, however big
    # the fire gets, because the smoke reading gates the CO one.
    def test_a_dead_smoke_detector_does_not_blind_the_system(self):
        result = run("blind-spot")
        self.assertTrue(result.alarmed())
        self.assertEqual(result.score["detections"], 1)
        self.assertEqual(result.score["false_alarms"], 0)

    # Losing a modality should cost time, not the detection itself.
    def test_a_dead_smoke_detector_costs_time(self):
        self.assertGreater(
            run("blind-spot").score["worst_latency"],
            run("office-fire").score["worst_latency"],
        )

    # A fire held down by the water it called for is reported as held, not as out.
    def test_a_held_fire_is_reported_as_suppressed(self):
        self.assertIn("SUPPRESSED", run("blind-spot").states)


if __name__ == "__main__":
    unittest.main()
