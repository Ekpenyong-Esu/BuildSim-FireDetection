"""The agent is a per-room state machine with dwell times to prevent flicker."""

import unittest

from firelab.domain import agent


class TestAgent(unittest.TestCase):
    # Sustained high probability must walk all the way up to CONFIRMED and act.
    def test_escalates_through_every_state(self):
        room = agent.RoomAgent(space="level0/A1")
        thresholds = agent.Thresholds()
        seen = [room.state]
        commands = []
        for t in range(0, 400, 5):
            commands += agent.update(room, 0.9, float(t), thresholds)
            if room.state != seen[-1]:
                seen.append(room.state)
        self.assertEqual(seen, ["NORMAL", "INVESTIGATING", "PRE_ALARM", "CONFIRMED"])
        self.assertTrue(any(c.kind == "sprinkler" and c.value == "on" for c in commands))

    # A transient spike must not reach CONFIRMED.
    def test_transient_never_confirms(self):
        room = agent.RoomAgent(space="level0/A1")
        thresholds = agent.Thresholds()
        for t in range(0, 200, 5):
            agent.update(room, 0.4, float(t), thresholds)
        self.assertEqual(room.state, "INVESTIGATING")

    # An interlock saying "not yet" is a delay, so the request keeps coming back
    # until something retires it. Otherwise it is asked for exactly once, at the
    # least convenient moment, and then silently forgotten.
    def test_an_unretired_command_is_offered_again_every_tick(self):
        room = agent.RoomAgent(space="level0/A1")
        thresholds = agent.Thresholds()
        for t in range(0, 400, 5):
            agent.update(room, 0.9, float(t), thresholds)
        self.assertEqual(room.state, "CONFIRMED")

        later = agent.update(room, 0.9, 405.0, thresholds)
        self.assertIn("sprinkler", [c.kind for c in later])

        agent.retire(room, agent.Command("sprinkler", room.space, "on", "done"))
        after = agent.update(room, 0.9, 410.0, thresholds)
        self.assertNotIn("sprinkler", [c.kind for c in after])

    # Water on the fire plus evidence that stays down is suppression, not silence.
    def test_a_sprinkler_that_holds_the_fire_reaches_suppressed(self):
        room = agent.RoomAgent(space="level0/A1")
        thresholds = agent.Thresholds()
        for t in range(0, 400, 5):
            agent.update(room, 0.9, float(t), thresholds)
        agent.retire(room, agent.Command("sprinkler", room.space, "on", "done"))
        for t in range(400, 500, 5):
            agent.update(room, 0.5, float(t), thresholds)  # knocked down, not out
        self.assertEqual(room.state, "SUPPRESSED")

    # A room that stood down has to become ordinary again, or it stays coloured
    # in as an incident in the viewer for the rest of the run.
    def test_a_cleared_room_returns_to_normal(self):
        room = agent.RoomAgent(space="level0/A1")
        thresholds = agent.Thresholds()
        for t in range(0, 400, 5):
            agent.update(room, 0.9, float(t), thresholds)
        for t in range(400, 700, 5):
            agent.update(room, 0.0, float(t), thresholds)
        self.assertEqual(room.state, "NORMAL")


if __name__ == "__main__":
    unittest.main()
