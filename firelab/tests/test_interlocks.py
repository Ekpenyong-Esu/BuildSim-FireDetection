"""Check that automatic and manual commands follow safety rules."""

import unittest

from firelab.domain import agent, interlocks


class TestInterlocks(unittest.TestCase):
    # Water needs heat corroboration: smoke alone must not release it.
    def test_smoke_alone_does_not_release_water(self):
        command = agent.Command("sprinkler", "level0/A1", "on", "")
        self.assertFalse(interlocks.check(command, 22.0, 0, False).allowed)
        self.assertTrue(interlocks.check(command, 80.0, 0, False).allowed)

    # Fire doors must fail unlocked, always.
    def test_fire_doors_never_lock(self):
        command = agent.Command("fire_door", "level0/A1", "locked", "")
        self.assertFalse(interlocks.check(command, 80.0, 0, False).allowed)

    # Cannot seal a room that is occupied or on an escape route.
    def test_cannot_seal_an_occupied_room_or_a_route(self):
        command = agent.Command("fire_door", "level0/A1", "closed", "")
        self.assertFalse(interlocks.check(command, 80.0, 3, False).allowed)
        self.assertFalse(interlocks.check(command, 80.0, 0, True).allowed)
        self.assertTrue(interlocks.check(command, 80.0, 0, False).allowed)


if __name__ == "__main__":
    unittest.main()


class TestStandingDownNextToAFire(unittest.TestCase):
    """A neighbour's own sprinkler makes its readings look safe; the fire next door has not moved."""

    def test_no_standing_down_beside_an_alarming_room(self):
        for kind, value in (("sprinkler", "off"), ("fire_door", "open")):
            with self.subTest(kind=kind):
                command = agent.Command(kind, "level0/A", value, "clearing")
                self.assertFalse(interlocks.check(command, 30.0, 0, False, neighbours_alarming=1).allowed)
                self.assertTrue(interlocks.check(command, 30.0, 0, False, neighbours_alarming=0).allowed)

    def test_raising_the_alarm_is_never_held_back_by_a_neighbour(self):
        command = agent.Command("sprinkler", "level0/A", "on", "confirmed")
        self.assertTrue(interlocks.check(command, 80.0, 0, False, neighbours_alarming=3).allowed)
