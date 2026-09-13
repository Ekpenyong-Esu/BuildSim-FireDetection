"""Telling BuildSim which rooms are alight, so its router avoids them.

BuildSim's walkable router drops the entries of any door marked `blocked` from
the graph. Publishing our belief there is what turns "reject the path BuildSim
handed us" into "ask BuildSim for a path that goes round", which is the
difference between losing a whole exit and finding the detour to it.
"""

import unittest

from firelab.adapters.publisher import doors

from .helpers import make_world

A1, A2 = "level0/A1", "level0/A2"


class TestDoorPublishing(unittest.TestCase):
    def setUp(self):
        self.world = make_world()

    def test_an_alarming_room_is_published_blocked(self):
        payload = doors(self.world, {}, {A1})
        self.assertEqual(len(payload), 1)
        self.assertTrue(payload[0]["blocked"])
        self.assertEqual(payload[0]["room"], "A1")

    def test_a_quiet_room_with_a_commanded_door_is_not_blocked(self):
        payload = doors(self.world, {A1: "closed"}, set())
        self.assertFalse(payload[0]["blocked"])
        self.assertEqual(payload[0]["state"], "closed")

    def test_an_alarming_room_needs_no_door_to_be_published(self):
        # Routing has to avoid a burning room whether or not anyone ever
        # commanded a fire door there.
        rooms = {d["room"] for d in doors(self.world, {}, {A1, A2})}
        self.assertEqual(rooms, {"A1", "A2"})

    def test_a_room_that_is_both_commanded_and_alight_appears_once(self):
        payload = doors(self.world, {A1: "closed"}, {A1})
        self.assertEqual(len(payload), 1)
        self.assertTrue(payload[0]["blocked"])

    def test_fire_doors_are_never_locked(self):
        # The interlock refuses to lock one; publishing must not do it either.
        payload = doors(self.world, {A1: "closed"}, {A2})
        self.assertTrue(all(d["lock_state"] == "unlocked" for d in payload))

    def test_an_unknown_room_is_skipped(self):
        self.assertEqual(doors(self.world, {}, {"level9/NOWHERE"}), [])

    def test_nothing_alight_and_nothing_commanded_publishes_nothing(self):
        self.assertEqual(doors(self.world, {}, set()), [])

    def test_the_order_is_stable(self):
        # Publishing compares against what was sent last; a set's iteration
        # order would make an unchanged building look like it kept changing.
        first = doors(self.world, {A2: "open"}, {A1})
        second = doors(self.world, {A2: "open"}, {A1})
        self.assertEqual(first, second)
        self.assertEqual([d["room"] for d in first], ["A1", "A2"])


if __name__ == "__main__":
    unittest.main()
