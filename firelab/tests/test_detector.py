"""The detector must separate real fires from nuisances on readings alone."""

import unittest

from firelab.domain import features
from firelab.domain.detector import FusionRule


class TestDetector(unittest.TestCase):
    def setUp(self):
        self.detector = FusionRule()

    def _features(self, **kwargs):
        return features.Features(space="level0/A1", coverage=3, **kwargs)

    # A quiet room must not alarm.
    def test_quiet_room_is_near_zero(self):
        self.assertLess(self.detector.probability(self._features()), 0.1)

    # No sensors means no opinion, not a low probability.
    def test_no_coverage_is_zero(self):
        self.assertEqual(self.detector.probability(features.Features(space="level0/A1")), 0.0)

    # A real fire must score higher than dust, which is smoke without heat or CO.
    def test_fire_beats_dust(self):
        fire = self._features(smoke=0.8, co=600.0, temperature=70.0, temperature_rise=50.0,
                              smoke_rate=0.5, co_smoke_ratio=750.0)
        dust = self._features(smoke=0.4, co=0.0, temperature=20.5, temperature_rise=0.5,
                              smoke_rate=0.4, co_smoke_ratio=0.0)
        self.assertGreater(self.detector.probability(fire), self.detector.probability(dust))

    # Smouldering has little heat; CO-to-smoke ratio must carry it.
    def test_smouldering_is_caught_by_co(self):
        # Barely warmer than the room, but the CO-to-smoke ratio gives it away.
        smouldering = self._features(smoke=0.43, co=404.0, temperature=27.4,
                                     temperature_rise=7.4, co_smoke_ratio=940.0)
        self.assertGreater(self.detector.probability(smouldering), 0.8)

    # Cooking is the classic false alarm; it must stay below pre-alarm.
    def test_cooking_stays_below_pre_alarm(self):
        cooking = self._features(smoke=0.2, co=14.0, temperature=23.0, temperature_rise=3.0,
                                 smoke_rate=0.1, co_smoke_ratio=70.0)
        self.assertLess(self.detector.probability(cooking), 0.4)

    # Trace smoke with background CO must not trigger on ratio alone.
    def test_trace_smoke_with_background_co_stays_quiet(self):
        # A neighbouring room drifting up to 0.02 1/m must not alarm on the ratio.
        trace = self._features(smoke=0.02, co=19.0, temperature=20.2, temperature_rise=0.2,
                               co_smoke_ratio=950.0)
        self.assertLess(self.detector.probability(trace), 0.2)


if __name__ == "__main__":
    unittest.main()
