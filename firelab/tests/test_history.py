"""History is a rolling record for charts and CSV export."""

import unittest

from firelab.domain import history


class TestHistory(unittest.TestCase):
    # The record must stay bounded and must not oversample when time barely moves.
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


if __name__ == "__main__":
    unittest.main()
