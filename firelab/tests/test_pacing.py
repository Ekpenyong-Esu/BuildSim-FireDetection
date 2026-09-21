"""The engine never runs the clock faster than its detector can answer."""

import unittest

from firelab.app.config import Config
from firelab.app.engine.core import Engine


class Slow:
    """A detector that has measured how fast it can go."""

    name = "slow"

    def __init__(self, limit):
        self.limit = limit

    def max_speed(self):
        return self.limit

    def probability(self, features):
        return 0.0

    def explain(self, features):
        return []


class TestPacing(unittest.TestCase):
    def setUp(self):
        self.engine = Engine(Config())

    def test_the_rule_has_no_speed_limit(self):
        self.engine.config.factor = 60.0
        self.engine._pace_for_detector()
        self.assertEqual(self.engine.config.factor, 60.0)

    def test_a_slow_detector_caps_the_dial_and_says_so_once(self):
        self.engine.detector = Slow(4.6)
        self.engine.config.factor = 40.0
        self.engine._pace_for_detector()
        self.engine._pace_for_detector()
        self.assertEqual(self.engine.config.factor, 4.0)
        capped = [line for line in self.engine.journal if "speed capped" in line["message"]]
        self.assertEqual(len(capped), 1)

    def test_a_dial_under_the_cap_is_left_alone(self):
        self.engine.detector = Slow(4.6)
        self.engine.config.factor = 2.0
        self.engine._pace_for_detector()
        self.assertEqual(self.engine.config.factor, 2.0)

    def test_switching_back_to_the_rule_lifts_the_cap(self):
        self.engine.detector = Slow(3.0)
        self.engine.config.factor = 40.0
        self.engine._pace_for_detector()
        self.engine.detector = Engine(Config()).detector  # the rule
        self.engine.config.factor = 40.0
        self.engine._pace_for_detector()
        self.assertEqual(self.engine.config.factor, 40.0)


if __name__ == "__main__":
    unittest.main()
