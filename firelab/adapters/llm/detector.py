"""The LLM as a `Detector`: cached verdicts, background questions, rule fallback.

`probability()` is called for every monitored room on every tick and must
answer at once. It returns the model's last fresh verdict for the room, or the
fusion rule's number when there is none, and at most schedules a new question.
A worker task asks the questions, a few at a time, off the tick loop.

Failure is the rule taking over, never a stall: a timeout, a bad reply or a
missing verdict all mean the room is scored by the rule until the model has
something fresh to say, and the journal records the change each way.
"""

import asyncio
import math
import statistics
import time
from collections.abc import Callable
from typing import Protocol

from openai.types.chat import ChatCompletionMessageParam

from ...domain.detector import Contribution, Detector
from ...domain.features import Features
from . import policy as policy_mod
from . import prompt
from .client import LLMError
from .policy import RefreshPolicy
from .verdict import Verdict, VerdictError, parse

Clock = Callable[[], float]  # simulated seconds; injected so the detector owns no clock
Log = Callable[[str, str], None]  # (kind, message), the engine's journal


class Completer(Protocol):
    """What the detector needs from a client: messages in, JSON text out."""

    async def complete_json(self, messages: list[ChatCompletionMessageParam]) -> str: ...


class LLMDetector:
    """Scores rooms with a language model, without ever making the tick wait."""

    name = "llm"

    def __init__(
        self,
        completer: Completer,
        clock: Clock,
        fallback: Detector,
        policy: RefreshPolicy | None = None,
        log: Log | None = None,
        max_concurrency: int = 4,
    ) -> None:
        self._completer = completer
        self._clock = clock
        self._fallback = fallback
        self._policy = policy or RefreshPolicy()
        self._log = log or (lambda kind, message: None)
        self._limit = asyncio.Semaphore(max_concurrency)
        self._verdicts: dict[str, Verdict] = {}  # room -> the model's latest opinion
        self._asked: dict[str, float] = {}  # room -> when it was last asked about
        self._pending: dict[str, Features] = {}  # room -> readings waiting to be sent; latest wins
        self._fallback_rooms: set[str] = set()  # rooms the rule is scoring right now, for the journal
        self._journaled: dict[str, float] = {}  # room -> the last verdict written to the journal
        self._late_rooms: set[str] = set()  # rooms whose answers arrive after they have expired
        self._in_flight: set[str] = set()  # rooms with a question out; not asked again meanwhile
        self._latencies: list[float] = []  # real seconds per answer, the last few, for pacing
        self._counts = {"asked": 0, "answered": 0, "failed": 0}  # over the detector's life, for the harness
        self._all_latencies: list[float] = []  # every answer's real seconds, for the harness
        self._task: asyncio.Task | None = None

    # --- the Detector protocol: answers at once, never waits ------------------

    def probability(self, features: Features) -> float:
        """The model's fresh verdict for the room, else the rule's number."""
        if features.coverage == 0:
            return 0.0  # no working sensor: no opinion, same as the rule
        self._schedule(features)
        verdict = self._fresh(features.space)
        if verdict is None:
            self._note_fallback(features.space, True)
            return self._fallback.probability(features)
        self._note_fallback(features.space, False)
        return verdict.p_fire

    def explain(self, features: Features) -> list[Contribution]:
        """The model's evidence as contributions, or the rule's terms when it is in charge."""
        verdict = self._fresh(features.space)
        if verdict is None:
            return self._fallback.explain(features)
        terms = [Contribution(item.name, item.weight, item.weight) for item in verdict.evidence]
        # The verdict itself, on the same logit scale the rule's terms use, so the
        # bar chart reads the same whichever detector is installed.
        terms.append(Contribution("model verdict", verdict.p_fire, _logit(verdict.p_fire)))
        return terms

    # --- lifecycle: the worker runs beside the tick loop ------------------------

    async def start(self) -> None:
        """Start asking questions in the background."""
        if self._task is None:
            self._task = asyncio.create_task(self._work())

    async def stop(self) -> None:
        """Stop the worker; anything still pending is dropped."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    # --- scheduling ----------------------------------------------------------------

    def _schedule(self, features: Features) -> None:
        """Queue a question for the room if it is worth asking, due, and not already out."""
        if policy_mod.is_quiet(self._policy, features):
            return
        if features.space in self._in_flight:
            return  # asking again before the answer is back only lengthens the queue
        if not policy_mod.is_due(self._policy, self._asked.get(features.space), self._clock()):
            return
        self._pending[features.space] = features
        self._asked[features.space] = self._clock()

    def max_speed(self) -> float | None:
        """How many times real time the model can keep up with, from what it has shown.

        A verdict is good for `max_age` simulated seconds and the model takes
        about `latency` real seconds to produce one, so the clock may run at
        most `max_age / latency` times real time; half that leaves room for the
        odd slow answer. None until a few answers have been timed.
        """
        if len(self._latencies) < 2:
            return None
        latency = statistics.median(self._latencies)
        return max(1.0, self._policy.max_age / (2.0 * max(latency, 0.1)))

    def in_charge(self, room: str) -> bool:
        """Whether the room's score right now is the model's own rather than the rule's."""
        return self._fresh(room) is not None

    def stats(self) -> dict:
        """What the model has cost so far: questions, answers, failures and how long answers took."""
        timed = sorted(self._all_latencies)
        return {
            **self._counts,
            "latency_median_s": round(statistics.median(timed), 2) if timed else None,
            "latency_max_s": round(timed[-1], 2) if timed else None,
            "max_speed": self.max_speed(),
        }

    def _fresh(self, room: str) -> Verdict | None:
        verdict = self._verdicts.get(room)
        if verdict is None or not policy_mod.is_fresh(self._policy, verdict.at, self._clock()):
            return None
        return verdict

    async def _work(self) -> None:
        """Send whatever is pending, a bounded number at a time, forever."""
        while True:
            await asyncio.sleep(0.25)
            await self.refresh_pending()

    async def refresh_pending(self) -> None:
        """Ask about every room queued so far, most suspicious first. Public so tests can drive it."""
        batch, self._pending = self._pending, {}
        if not batch:
            return
        # The rule's own score is a cheap, sensible order: the room that looks most
        # like a fire gets its answer before its quiet neighbours do.
        ordered = sorted(batch.items(), key=lambda item: self._fallback.probability(item[1]), reverse=True)
        self._in_flight.update(room for room, _ in ordered)
        await asyncio.gather(*(self._ask(room, features) for room, features in ordered))

    async def _ask(self, room: str, features: Features) -> None:
        """One question, one answer, stored if it parses; otherwise the rule stays in charge."""
        asked_at = self._clock()
        started = time.monotonic()
        self._counts["asked"] += 1
        try:
            async with self._limit:
                answering = time.monotonic()
                try:
                    text = await self._completer.complete_json(prompt.messages(features))
                    verdict = parse(text, asked_at)
                except (LLMError, VerdictError) as exc:
                    self._counts["failed"] += 1
                    self._log("detector", f"{room}: model unavailable ({exc}); the rule is scoring it")
                    return
                self._counts["answered"] += 1
                self._latencies = (self._latencies + [time.monotonic() - answering])[-5:]
                self._all_latencies.append(self._latencies[-1])
        finally:
            self._in_flight.discard(room)
        self._verdicts[room] = verdict
        # Against the last verdict *journaled*, not the last one given: a score that
        # creeps up by 0.09 an answer would otherwise never be written down at all.
        last = self._journaled.get(room)
        if last is None or abs(last - verdict.p_fire) >= 0.1:
            self._journaled[room] = verdict.p_fire
            self._log("detector", f"{room}: model says P(fire)={verdict.p_fire:.2f}: {verdict.reason}")
        self._note_lag(room, self._clock() - asked_at, time.monotonic() - started)

    def _note_lag(self, room: str, simulated: float, real: float) -> None:
        """Say so, once, when answers arrive too late to be used at the current speed.

        A verdict is only used while its readings are younger than `max_age`
        simulated seconds. Run the clock fast enough and every answer is stale
        on arrival, the rule scores everything, and nothing in the journal
        would explain why. This line does, and says what speed would work.
        """
        late = simulated > self._policy.max_age
        if late and room not in self._late_rooms:
            self._late_rooms.add(room)
            factor = max(1, int(self._policy.max_age / max(real, 0.1)))
            self._log(
                "detector",
                f"{room}: the model answered {real:.0f} s later, which is {simulated:.0f} simulated seconds "
                f"at this speed; its verdict expired before it arrived and the rule is scoring the room. "
                f"It can keep up at about {factor}x or slower; the speed is being capped to match, "
                f"or raise max_age_seconds.",
            )
        elif not late and room in self._late_rooms:
            self._late_rooms.discard(room)
            self._log("detector", f"{room}: model answers are arriving in time again")

    def _note_fallback(self, room: str, falling_back: bool) -> None:
        """Journal the moment the rule takes over a room, and the moment it hands back."""
        if falling_back and room not in self._fallback_rooms:
            self._fallback_rooms.add(room)
            if room in self._verdicts:  # the model had spoken and its word has expired
                self._log("detector", f"{room}: model verdict expired; the rule is scoring the room")
        elif not falling_back and room in self._fallback_rooms:
            self._fallback_rooms.discard(room)
            self._log("detector", f"{room}: model verdict in use")


def _logit(p: float) -> float:
    """The rule's raw score for a probability, clipped away from 0 and 1."""
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))
