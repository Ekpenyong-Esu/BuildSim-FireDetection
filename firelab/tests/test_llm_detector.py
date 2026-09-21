"""The LLM detector never makes the tick wait, and the rule covers every gap.

No endpoint is involved: a fake completer answers instantly with whatever JSON
the test wants, and the worker is driven by hand.
"""

import asyncio
import json
import unittest

from firelab.adapters.llm import LLMDetector, LLMError, RefreshPolicy, VerdictError
from firelab.adapters.llm import policy as policy_mod
from firelab.adapters.llm import prompt, verdict
from firelab.domain.detector import FusionRule
from firelab.domain.features import Features


class FakeCompleter:
    """Answers with a canned reply, or raises, and counts how often it was asked."""

    def __init__(self, reply=None, error=None):
        self.reply = reply
        self.error = error
        self.asked = []

    async def complete_json(self, messages):
        self.asked.append(messages)
        if self.error is not None:
            raise self.error
        return self.reply


class FakeClock:
    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now


def smoky(space="level0/A1", coverage=3):
    """Readings a fire would produce: the rule scores these high."""
    return Features(space=space, smoke=0.4, co=90.0, temperature=60.0, smoke_rate=0.3,
                    temperature_rise=40.0, co_smoke_ratio=225.0, neighbour_agreement=0.5, coverage=coverage)


def quiet(space="level0/A1"):
    return Features(space=space, coverage=3)


def reply(p, reason="smoke and CO rising together"):
    return json.dumps({"p_fire": p, "evidence": [{"name": "co", "weight": 1.2}, {"name": "smoke", "weight": 2.0}],
                       "reason": reason})


def detector(completer, clock, **policy):
    return LLMDetector(completer, clock, FusionRule(), RefreshPolicy(**policy), log=lambda k, m: None)


class TestVerdictParsing(unittest.TestCase):
    def test_a_good_reply_becomes_a_verdict_with_evidence_sorted(self):
        v = verdict.parse(reply(0.8), at=5.0)
        self.assertEqual(v.p_fire, 0.8)
        self.assertEqual([e.name for e in v.evidence], ["smoke", "co"])
        self.assertEqual(v.at, 5.0)

    def test_probability_is_clamped_and_reason_trimmed(self):
        v = verdict.parse(json.dumps({"p_fire": 1.7, "reason": "  a   b  " + "x" * 500}), at=0.0)
        self.assertEqual(v.p_fire, 1.0)
        self.assertLessEqual(len(v.reason), verdict.REASON_LIMIT)
        self.assertTrue(v.reason.startswith("a b"))

    def test_bad_replies_are_refused_not_guessed(self):
        for text in ("not json", "[1, 2]", json.dumps({"p_fire": "high"}), json.dumps({"p_fire": True})):
            with self.subTest(text=text):
                with self.assertRaises(VerdictError):
                    verdict.parse(text, at=0.0)


class TestPromptAndPolicy(unittest.TestCase):
    def test_the_prompt_carries_readings_only(self):
        text = prompt.describe(smoky())
        self.assertIn("Smoke: 0.400", text)
        self.assertIn("CO: 90 ppm", text)
        self.assertNotIn("truth", text.lower())

    def test_quiet_rooms_are_not_worth_asking_about(self):
        p = RefreshPolicy()
        self.assertTrue(policy_mod.is_quiet(p, quiet()))
        self.assertFalse(policy_mod.is_quiet(p, smoky()))

    def test_due_and_fresh_follow_the_clock(self):
        p = RefreshPolicy(every=10.0, max_age=60.0)
        self.assertTrue(policy_mod.is_due(p, None, 0.0))
        self.assertFalse(policy_mod.is_due(p, 5.0, 12.0))
        self.assertTrue(policy_mod.is_due(p, 5.0, 15.0))
        self.assertTrue(policy_mod.is_fresh(p, 0.0, 60.0))
        self.assertFalse(policy_mod.is_fresh(p, 0.0, 61.0))


class TestLLMDetector(unittest.IsolatedAsyncioTestCase):
    async def test_the_rule_answers_until_the_model_has_spoken(self):
        completer, clock = FakeCompleter(reply(0.9)), FakeClock()
        d = detector(completer, clock)
        first = d.probability(smoky())
        self.assertEqual(first, FusionRule().probability(smoky()))  # nothing fresh yet: the rule
        self.assertEqual(completer.asked, [])  # and nothing was sent inside the tick
        await d.refresh_pending()
        self.assertEqual(len(completer.asked), 1)
        self.assertEqual(d.probability(smoky()), 0.9)

    async def test_a_quiet_room_never_costs_a_question(self):
        completer, clock = FakeCompleter(reply(0.1)), FakeClock()
        d = detector(completer, clock)
        d.probability(quiet())
        await d.refresh_pending()
        self.assertEqual(completer.asked, [])

    async def test_a_room_is_asked_about_at_most_once_per_interval(self):
        completer, clock = FakeCompleter(reply(0.5)), FakeClock()
        d = detector(completer, clock, every=10.0)
        for clock.now in (0.0, 3.0, 6.0, 9.0):
            d.probability(smoky())
            await d.refresh_pending()
        self.assertEqual(len(completer.asked), 1)
        clock.now = 10.0
        d.probability(smoky())
        await d.refresh_pending()
        self.assertEqual(len(completer.asked), 2)

    async def test_a_stale_verdict_hands_back_to_the_rule(self):
        completer, clock = FakeCompleter(reply(0.95)), FakeClock()
        d = detector(completer, clock, every=10.0, max_age=30.0)
        d.probability(smoky())
        await d.refresh_pending()
        self.assertEqual(d.probability(smoky()), 0.95)
        clock.now = 31.0
        completer.error = LLMError("endpoint down")  # the refresh that is now due will fail
        self.assertEqual(d.probability(smoky()), FusionRule().probability(smoky()))
        await d.refresh_pending()
        self.assertEqual(d.probability(smoky()), FusionRule().probability(smoky()))

    async def test_a_bad_reply_leaves_the_rule_in_charge(self):
        completer, clock = FakeCompleter("no json here"), FakeClock()
        d = detector(completer, clock)
        d.probability(smoky())
        await d.refresh_pending()
        self.assertEqual(d.probability(smoky()), FusionRule().probability(smoky()))

    async def test_no_sensor_means_no_opinion(self):
        d = detector(FakeCompleter(reply(0.9)), FakeClock())
        self.assertEqual(d.probability(smoky(coverage=0)), 0.0)

    async def test_explain_shows_the_models_evidence_once_it_is_in_charge(self):
        completer, clock = FakeCompleter(reply(0.8)), FakeClock()
        d = detector(completer, clock)
        d.probability(smoky())
        await d.refresh_pending()
        names = [term.name for term in d.explain(smoky())]
        self.assertEqual(names, ["smoke", "co", "model verdict"])

    async def test_the_worker_starts_and_stops_cleanly(self):
        d = detector(FakeCompleter(reply(0.3)), FakeClock())
        await d.start()
        await d.start()  # idempotent
        await asyncio.sleep(0)
        await d.stop()
        await d.stop()



class SlowCompleter(FakeCompleter):
    """Answers correctly, but the simulated clock races ahead while it thinks."""

    def __init__(self, reply, clock, advance):
        super().__init__(reply)
        self.clock, self.advance = clock, advance

    async def complete_json(self, messages):
        self.clock.now += self.advance
        return await super().complete_json(messages)


class TestLag(unittest.IsolatedAsyncioTestCase):
    async def test_an_answer_that_expires_in_flight_is_reported_once_and_not_used(self):
        clock, lines = FakeClock(), []
        completer = SlowCompleter(reply(0.9), clock, advance=700.0)  # 45x with a 15 s answer
        d = LLMDetector(completer, clock, FusionRule(), RefreshPolicy(every=10.0, max_age=60.0),
                        log=lambda kind, message: lines.append(message))
        d.probability(smoky())
        await d.refresh_pending()
        self.assertEqual(d.probability(smoky()), FusionRule().probability(smoky()))  # stale: the rule
        late = [m for m in lines if "expired before it arrived" in m]
        self.assertEqual(len(late), 1)
        self.assertIn("or slower", late[0])
        d.probability(smoky())  # another interval is due at once; the second late answer stays quiet
        await d.refresh_pending()
        self.assertEqual(len([m for m in lines if "expired before it arrived" in m]), 1)

class TestPacing(unittest.IsolatedAsyncioTestCase):
    async def test_a_room_with_a_question_out_is_not_asked_again(self):
        clock = FakeClock()
        gate = asyncio.Event()

        class Blocking(FakeCompleter):
            async def complete_json(self, messages):
                self.asked.append(messages)
                await gate.wait()
                return reply(0.5)

        completer = Blocking()
        d = detector(completer, clock, every=1.0)
        d.probability(smoky())
        task = asyncio.create_task(d.refresh_pending())
        for _ in range(20):  # let the worker reach the (blocked) endpoint call
            await asyncio.sleep(0)
            if completer.asked:
                break
        clock.now = 5.0
        d.probability(smoky())  # due again, but the first question is still out
        await d.refresh_pending()
        self.assertEqual(len(completer.asked), 1)
        gate.set()
        await task

    async def test_the_most_suspicious_room_is_asked_first(self):
        order = []

        class Recording(FakeCompleter):
            async def complete_json(self, messages):
                order.append(messages[1]["content"].split(".")[0])
                return reply(0.5)

        d = LLMDetector(Recording(), FakeClock(), FusionRule(), RefreshPolicy(), log=lambda k, m: None, max_concurrency=1)
        d.probability(Features(space="level0/QUIETISH", smoke=0.05, co=10.0, coverage=3))
        d.probability(smoky("level0/BURNING"))
        await d.refresh_pending()
        self.assertEqual(order[0], "Room level0/BURNING")

    async def test_max_speed_comes_from_measured_answers(self):
        d = detector(FakeCompleter(reply(0.5)), FakeClock(), max_age=60.0)
        self.assertIsNone(d.max_speed())  # nothing timed yet
        d._latencies = [5.0, 6.0, 5.0]  # median five seconds an answer
        self.assertAlmostEqual(d.max_speed(), 60.0 / (2 * 5.0))
        d._latencies = [200.0, 200.0]
        self.assertEqual(d.max_speed(), 1.0)  # never below real time


if __name__ == "__main__":
    unittest.main()
