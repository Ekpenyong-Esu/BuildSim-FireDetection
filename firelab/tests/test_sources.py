"""Sources define the ground truth; the detector must learn to tell them apart."""

import unittest

from firelab.domain import sources


class TestSources(unittest.TestCase):
    # Growth must be monotonic and never exceed the declared peak.
    def test_flaming_grows_and_caps(self):
        source = sources.Source("s", "flaming", "level0/A1", t_start=0, peak_kw=500)
        early = sources.emission(source, 30)[0]
        late = sources.emission(source, 600)[0]
        self.assertLess(early, late)
        self.assertLessEqual(late, 500)

    # Smouldering is the hard case: almost no heat, but very high CO.
    def test_smouldering_has_high_co_low_heat(self):
        source = sources.Source("s", "smouldering", "level0/A1", t_start=0)
        heat, smoke, co = sources.emission(source, 600)
        self.assertLess(heat, 5)
        self.assertGreater(co / smoke, 500)

    # Nuisances must not produce CO, or the detector has nothing to separate them with.
    def test_nuisances_produce_no_co(self):
        for kind in ("dust", "steam"):
            source = sources.Source("s", kind, "level0/A1", t_start=0)
            self.assertEqual(sources.emission(source, 60)[2], 0.0)


if __name__ == "__main__":
    unittest.main()
