"""The rule explains itself in the journal the way the model does."""

import unittest

from firelab.app.engine.intelligence import JOURNAL_STEP, material_change, rule_summary
from firelab.domain.detector import FusionRule
from firelab.domain.features import Features


class TestMaterialChange(unittest.TestCase):
    def test_a_quiet_room_never_gets_a_line(self):
        self.assertFalse(material_change(None, 0.05, floor=0.35))
        self.assertFalse(material_change(0.05, 0.12, floor=0.35))

    def test_the_first_time_the_score_matters_is_reported(self):
        self.assertTrue(material_change(None, 0.4, floor=0.35))
        self.assertTrue(material_change(0.1, 0.4, floor=0.35))

    def test_then_only_steps_of_a_tenth(self):
        self.assertFalse(material_change(0.4, 0.45, floor=0.35))
        self.assertTrue(material_change(0.4, 0.4 + JOURNAL_STEP, floor=0.35))
        self.assertTrue(material_change(0.9, 0.2, floor=0.35))  # falling back is news too


class TestRuleSummary(unittest.TestCase):
    def test_names_the_strongest_terms_and_skips_the_bias(self):
        fire = Features(space="level0/A", smoke=0.4, co=90.0, temperature=60.0, smoke_rate=0.3,
                        temperature_rise=40.0, co_smoke_ratio=225.0, neighbour_agreement=0.5, coverage=3)
        text = rule_summary(FusionRule().explain(fire))
        # A 40 degree rise is the rule's strongest term for these readings.
        self.assertTrue(text.startswith("temperature rise +"), text)
        self.assertIn("smoke +", text)
        self.assertNotIn("bias", text)
        self.assertLessEqual(text.count("+"), 3)

    def test_nothing_pushing(self):
        self.assertEqual(rule_summary(FusionRule().explain(Features(space="level0/A", coverage=3))),
                         "nothing pushing towards fire")


if __name__ == "__main__":
    unittest.main()
