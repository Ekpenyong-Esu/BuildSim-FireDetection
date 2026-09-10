"""Domain tests: no BuildSim, no network, no clock."""

import unittest
from random import Random

from firelab.domain import (
    agent,
    features,
    history,
    interlocks,
    occupants,
    physics,
    scoring,
    sensing,
    sources,
)
from firelab.domain.detector import FusionRule


def make_world() -> physics.World:
    world = physics.World()
    for name in ("A1", "A2"):
        world.spaces[f"level0/{name}"] = physics.Space(
            key=f"level0/{name}",
            level="level0",
            name=name,
            kind="room",
            area_m2=25.0,
            center=(0.0, 0.0),
        )
    world.couplings.append(physics.Coupling(a="level0/A1", b="level0/A2", conductance=0.5))
    return world


class TestSources(unittest.TestCase):
    def test_flaming_grows_and_caps(self):
        source = sources.Source("s", "flaming", "level0/A1", t_start=0, peak_kw=500)
        early = sources.emission(source, 30)[0]
        late = sources.emission(source, 600)[0]
        self.assertLess(early, late)
        self.assertLessEqual(late, 500)

    def test_smouldering_has_high_co_low_heat(self):
        source = sources.Source("s", "smouldering", "level0/A1", t_start=0)
        heat, smoke, co = sources.emission(source, 600)
        self.assertLess(heat, 5)
        self.assertGreater(co / smoke, 500)

    def test_nuisances_produce_no_co(self):
        for kind in ("dust", "steam"):
            source = sources.Source("s", kind, "level0/A1", t_start=0)
            self.assertEqual(sources.emission(source, 60)[2], 0.0)


class TestPhysics(unittest.TestCase):
    def test_heat_spreads_to_the_neighbour(self):
        world = make_world()
        for _ in range(600):
            physics.step(world, {"level0/A1": (300.0, 0.5, 400.0)}, 1.0)
        self.assertGreater(world.spaces["level0/A1"].temperature, physics.T_OUT)
        self.assertGreater(world.spaces["level0/A2"].smoke, 0.0)
        self.assertGreater(
            world.spaces["level0/A1"].smoke, world.spaces["level0/A2"].smoke
        )

    def test_sprinkler_suppresses(self):
        hot, wet = make_world(), make_world()
        wet.spaces["level0/A1"].sprinkler = True
        for _ in range(300):
            physics.step(hot, {"level0/A1": (300.0, 0.5, 0.0)}, 1.0)
            physics.step(wet, {"level0/A1": (300.0, 0.5, 0.0)}, 1.0)
        self.assertLess(
            wet.spaces["level0/A1"].temperature, hot.spaces["level0/A1"].temperature
        )


class TestSensing(unittest.TestCase):
    def test_reading_lags_and_then_tracks(self):
        rng = Random(0)
        device = sensing.Device.create("d1", "level0/A1", "temperature")
        device.noise = 0.0
        readings = [sensing.sample(device, 80.0, t, 1.0, rng) for t in range(600)]
        values = [r for r in readings if r is not None]
        self.assertLess(values[0], 40.0)
        self.assertGreater(values[-1], 75.0)

    def test_dead_device_reports_nothing(self):
        rng = Random(0)
        device = sensing.Device.create("d1", "level0/A1", "smoke", fault="dead")
        self.assertIsNone(sensing.sample(device, 1.0, 100.0, 1.0, rng))

    def test_stuck_device_repeats(self):
        rng = Random(0)
        device = sensing.Device.create("d1", "level0/A1", "smoke")
        first = None
        for t in range(0, 200, 5):
            value = sensing.sample(device, 0.9, float(t), 5.0, rng)
            if value is not None and first is None:
                first = value
                device.fault = "stuck"
        self.assertEqual(device.reading, first)


class TestDetector(unittest.TestCase):
    def setUp(self):
        self.detector = FusionRule()

    def _features(self, **kwargs):
        return features.Features(space="level0/A1", coverage=3, **kwargs)

    def test_quiet_room_is_near_zero(self):
        self.assertLess(self.detector.probability(self._features()), 0.1)

    def test_no_coverage_is_zero(self):
        self.assertEqual(self.detector.probability(features.Features(space="level0/A1")), 0.0)

    def test_fire_beats_dust(self):
        fire = self._features(smoke=0.8, co=600.0, temperature=70.0, temperature_rise=50.0,
                              smoke_rate=0.5, co_smoke_ratio=750.0)
        dust = self._features(smoke=0.4, co=0.0, temperature=20.5, temperature_rise=0.5,
                              smoke_rate=0.4, co_smoke_ratio=0.0)
        self.assertGreater(self.detector.probability(fire), self.detector.probability(dust))

    def test_smouldering_is_caught_by_co(self):
        # Barely warmer than the room, but the CO-to-smoke ratio gives it away.
        smouldering = self._features(smoke=0.43, co=404.0, temperature=27.4,
                                     temperature_rise=7.4, co_smoke_ratio=940.0)
        self.assertGreater(self.detector.probability(smouldering), 0.8)

    def test_cooking_stays_below_pre_alarm(self):
        cooking = self._features(smoke=0.2, co=14.0, temperature=23.0, temperature_rise=3.0,
                                 smoke_rate=0.1, co_smoke_ratio=70.0)
        self.assertLess(self.detector.probability(cooking), 0.4)

    def test_trace_smoke_with_background_co_stays_quiet(self):
        # A neighbouring room drifting up to 0.02 1/m must not alarm on the ratio.
        trace = self._features(smoke=0.02, co=19.0, temperature=20.2, temperature_rise=0.2,
                               co_smoke_ratio=950.0)
        self.assertLess(self.detector.probability(trace), 0.2)


class TestAgent(unittest.TestCase):
    def test_escalates_through_every_state(self):
        room = agent.RoomAgent(space="level0/A1")
        thresholds = agent.Thresholds()
        seen = [room.state]
        commands = []
        for t in range(0, 400, 5):
            commands += agent.update(room, 0.9, float(t), thresholds)
            if room.state != seen[-1]:
                seen.append(room.state)
        self.assertEqual(seen, ["NORMAL", "INVESTIGATING", "PRE_ALARM", "CONFIRMED"])
        self.assertTrue(any(c.kind == "sprinkler" and c.value == "on" for c in commands))

    def test_transient_never_confirms(self):
        room = agent.RoomAgent(space="level0/A1")
        thresholds = agent.Thresholds()
        for t in range(0, 200, 5):
            agent.update(room, 0.4, float(t), thresholds)
        self.assertEqual(room.state, "INVESTIGATING")


class TestInterlocks(unittest.TestCase):
    def test_smoke_alone_does_not_release_water(self):
        command = agent.Command("sprinkler", "level0/A1", "on", "")
        self.assertFalse(interlocks.check(command, 22.0, 0, False).allowed)
        self.assertTrue(interlocks.check(command, 80.0, 0, False).allowed)

    def test_fire_doors_never_lock(self):
        command = agent.Command("fire_door", "level0/A1", "locked", "")
        self.assertFalse(interlocks.check(command, 80.0, 0, False).allowed)

    def test_cannot_seal_an_occupied_room_or_a_route(self):
        command = agent.Command("fire_door", "level0/A1", "closed", "")
        self.assertFalse(interlocks.check(command, 80.0, 3, False).allowed)
        self.assertFalse(interlocks.check(command, 80.0, 0, True).allowed)
        self.assertTrue(interlocks.check(command, 80.0, 0, False).allowed)


class TestScoring(unittest.TestCase):
    def test_real_fire_scores_a_detection_with_latency(self):
        board = scoring.Scoreboard()
        source = sources.Source("s1", "flaming", "level0/A1", t_start=100.0)
        board.update(130.0, [source], {"level0/A1": "PRE_ALARM"})
        self.assertEqual(board.summary()["detections"], 0)
        board.update(160.0, [source], {"level0/A1": "CONFIRMED"})
        self.assertEqual(board.detected["s1"], 60.0)
        self.assertEqual(board.summary()["false_alarms"], 0)

    def test_alarming_on_cooking_is_a_false_alarm(self):
        board = scoring.Scoreboard()
        source = sources.Source("s1", "cooking", "level0/A1", t_start=0.0)
        board.update(60.0, [source], {"level0/A1": "CONFIRMED"})
        self.assertEqual(board.summary()["false_alarms"], 1)
        self.assertEqual(board.false_alarms[0].cause, "cooking")

    def test_a_fire_left_burning_counts_as_missed(self):
        board = scoring.Scoreboard()
        source = sources.Source("s1", "smouldering", "level0/A1", t_start=0.0)
        board.update(scoring.MISS_AFTER + 1, [source], {"level0/A1": "NORMAL"})
        self.assertIn("s1", board.missed)

    def test_spread_from_a_real_fire_is_not_a_false_alarm(self):
        board = scoring.Scoreboard()
        source = sources.Source("s1", "flaming", "level0/A1", t_start=0.0)
        board.update(60.0, [source], {"level0/A1": "CONFIRMED", "level0/A2": "CONFIRMED"})
        self.assertEqual(board.summary()["false_alarms"], 0)
        self.assertEqual(board.summary()["detections"], 1)


class TestHistory(unittest.TestCase):
    def test_samples_are_rate_limited_and_bounded(self):
        log = history.History()
        for step in range(history.MAX_POINTS * 2):
            log.record(step * history.SAMPLE_SECONDS, {"level0/A1": [1, 2, 3, 4, 5, 6, 0.5]})
        track = log.series("level0/A1")
        self.assertEqual(len(track), history.MAX_POINTS)
        self.assertEqual(len(track[0]), len(history.COLUMNS))

        before = len(log.series("level0/A1"))
        log.record(log._last + 0.1, {"level0/A1": [1, 2, 3, 4, 5, 6, 0.5]})
        self.assertEqual(len(log.series("level0/A1")), before)


class TestOccupants(unittest.TestCase):
    def test_everyone_lands_in_a_real_room(self):
        world = make_world()
        people = occupants.place(world.spaces.values(), {"student": 10}, Random(1))
        self.assertEqual(len(people), 10)
        for person in people:
            self.assertIn(person.space, world.spaces)

    def test_walking_consumes_waypoints_and_ends_safe(self):
        person = occupants.Occupant("o1", "O1", "level0/A1", [0.0, 0.0])
        person.route = [[10.0, 0.0], [10.0, 10.0]]
        person.route_spaces = ["level0/A2", ""]

        occupants.advance(person, 4.0)
        self.assertEqual(person.position, [4.0, 0.0])
        self.assertFalse(person.safe)

        occupants.advance(person, 100.0)
        self.assertEqual(person.space, "level0/A2")  # "" never overwrites the room
        self.assertTrue(person.safe)
        self.assertEqual(person.status, "safe")


if __name__ == "__main__":
    unittest.main()
