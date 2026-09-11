"""Scoring grades the system against the ground truth the sources carry."""

import unittest

from firelab.domain import scoring, sources


class TestScoring(unittest.TestCase):
    # Latency is measured from ignition to CONFIRMED, not to the first suspicion.
    def test_real_fire_scores_a_detection_with_latency(self):
        board = scoring.Scoreboard()
        source = sources.Source("s1", "flaming", "level0/A1", t_start=100.0)
        board.update(130.0, [source], {"level0/A1": "PRE_ALARM"})
        self.assertEqual(board.summary()["detections"], 0)
        board.update(160.0, [source], {"level0/A1": "CONFIRMED"})
        self.assertEqual(board.detected["s1"], 60.0)
        self.assertEqual(board.summary()["false_alarms"], 0)

    # Alarming on a nuisance is a false alarm.
    def test_alarming_on_cooking_is_a_false_alarm(self):
        board = scoring.Scoreboard()
        source = sources.Source("s1", "cooking", "level0/A1", t_start=0.0)
        board.update(60.0, [source], {"level0/A1": "CONFIRMED"})
        self.assertEqual(board.summary()["false_alarms"], 1)
        self.assertEqual(board.false_alarms[0].cause, "cooking")

    # A real fire left burning too long counts as missed.
    def test_a_fire_left_burning_counts_as_missed(self):
        board = scoring.Scoreboard()
        source = sources.Source("s1", "smouldering", "level0/A1", t_start=0.0)
        board.update(scoring.MISS_AFTER + 1, [source], {"level0/A1": "NORMAL"})
        self.assertIn("s1", board.missed)

    # Smoke spreading through the door from a real fire is not a false alarm.
    def test_spread_from_a_real_fire_is_not_a_false_alarm(self):
        board = scoring.Scoreboard()
        source = sources.Source("s1", "flaming", "level0/A1", t_start=0.0)
        board.update(
            60.0,
            [source],
            {"level0/A1": "CONFIRMED", "level0/A2": "CONFIRMED"},
            adjacency={"level0/A1": {"level0/A2"}, "level0/A2": {"level0/A1"}},
        )
        self.assertEqual(board.summary()["false_alarms"], 0)
        self.assertEqual(board.summary()["detections"], 1)

    # A fire elsewhere in the building is no excuse for an unconnected room.
    def test_a_fire_next_door_does_not_excuse_the_far_side_of_the_building(self):
        board = scoring.Scoreboard()
        source = sources.Source("s1", "flaming", "level0/A1", t_start=0.0)
        board.update(
            60.0,
            [source],
            {"level0/A1": "CONFIRMED", "level3/Z9": "CONFIRMED"},
            adjacency={"level0/A1": {"level0/A2"}, "level0/A2": {"level0/A1"}},
        )
        self.assertEqual(board.summary()["false_alarms"], 1)
        self.assertEqual(board.false_alarms[0].space, "level3/Z9")


if __name__ == "__main__":
    unittest.main()
