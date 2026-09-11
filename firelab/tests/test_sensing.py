"""Sensing is the truth-to-observation boundary; every blind spot is injected here."""

import unittest
from random import Random

from firelab.domain import sensing


class TestSensing(unittest.TestCase):
    # A real detector has thermal mass, so it lags before it tracks.
    def test_reading_lags_and_then_tracks(self):
        rng = Random(0)
        device = sensing.Device.create("d1", "level0/A1", "temperature")
        device.noise = 0.0
        readings = [sensing.sample(device, 80.0, t, 1.0, rng) for t in range(600)]
        values = [r for r in readings if r is not None]
        self.assertLess(values[0], 40.0)
        self.assertGreater(values[-1], 75.0)

    # Dead means silent forever, not a low value.
    def test_dead_device_reports_nothing(self):
        rng = Random(0)
        device = sensing.Device.create("d1", "level0/A1", "smoke", fault="dead")
        self.assertIsNone(sensing.sample(device, 1.0, 100.0, 1.0, rng))

    # Stuck looks alive but never updates — the detector must not trust it.
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


if __name__ == "__main__":
    unittest.main()
