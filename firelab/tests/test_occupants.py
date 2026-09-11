"""Occupants are scattered over routable rooms and walk along waypoints."""

import unittest
from random import Random

from firelab.domain import occupants

from .helpers import make_world


class TestOccupants(unittest.TestCase):
    # Nobody may be placed in a room that does not exist.
    def test_everyone_lands_in_a_real_room(self):
        world = make_world()
        people = occupants.place(world.spaces.values(), {"student": 10}, Random(1))
        self.assertEqual(len(people), 10)
        for person in people:
            self.assertIn(person.space, world.spaces)

    # Walking consumes waypoints and marks safe when the route is exhausted.
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
