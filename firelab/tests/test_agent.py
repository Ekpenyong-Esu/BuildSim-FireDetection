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


if __name__ == "__main__":
    unittest.main()
