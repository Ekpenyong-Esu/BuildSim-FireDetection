"""Grade the system against the ground truth the sources carry.

Every source knows whether it is a real fire or a nuisance, so the run can be
scored while it happens: how fast real fires were caught, which nuisances the
system fell for, and which fires it missed. Whether people got out *in time* is
a separate question, kept in `timeline.py`. Pure: it is told the time.
"""

from dataclasses import dataclass, field

from .sources import Source
from .timeline import Timeline

REAL = ("flaming", "smouldering")  # everything else is a nuisance
ALARM_STATES = ("CONFIRMED", "SUPPRESSED")  # the states that count as alarming
MISS_AFTER = 300.0  # a real fire burning this long unconfirmed counts as missed


@dataclass
class FalseAlarm:
    """An alarm in a room where nothing dangerous was happening."""

    space: str
    at: float
    cause: str  # the nuisance that fooled it, or "none"


@dataclass
class Scoreboard:
    """The running tally: what was caught, what was missed, what it fell for."""

    detected: dict[str, float] = field(default_factory=dict)  # source id -> seconds to confirm
    missed: set[str] = field(default_factory=set)  # source ids
    false_alarms: list[FalseAlarm] = field(default_factory=list)
    timeline: Timeline = field(default_factory=Timeline)
    _alarming: set[str] = field(default_factory=set)  # rooms alarming last tick

    def clear(self) -> None:
        """Start a fresh run with an empty scorecard."""
        self.detected.clear()
        self.missed.clear()
        self.false_alarms.clear()
        self._alarming.clear()
        self.timeline.clear()

    def update(
        self,
        now: float,
        sources: list[Source],
        states: dict[str, str],
        evacuating: int = 0,
        inside: int = 0,
        adjacency: dict[str, set[str]] | None = None,
    ) -> None:
        """Mark the system's homework for this tick."""
        # Compare with last tick so each alarm is only judged once, when raised.
        alarming = {key for key, state in states.items() if state in ALARM_STATES}
        for space in alarming - self._alarming:  # a newly raised alarm
            self._score_alarm(space, now, sources, adjacency or {})
        self._alarming = alarming

        self.timeline.note_alarm(now, bool(alarming))
        self.timeline.note_ignition([s.t_start for s in sources if s.kind in REAL and s.t_start <= now])
        self.timeline.note_evacuation(now, evacuating, inside)

        # A real fire nobody has confirmed after five minutes counts as missed.
        for source in sources:
            if source.kind not in REAL or source.id in self.detected:
                continue
            if now - source.t_start > MISS_AFTER:
                self.missed.add(source.id)

    def _score_alarm(
        self, space: str, now: float, sources: list[Source], adjacency: dict[str, set[str]]
    ) -> None:
        """Decide whether one new alarm was a good call or a false one."""
        lit = [s for s in sources if s.t_start <= now]  # already burning
        burning = [s for s in lit if s.space == space]  # ...in this room
        real = [s for s in burning if s.kind in REAL]
        if real:
            # A catch. Record how long it took, in seconds since ignition.
            for source in real:
                self.detected.setdefault(source.id, max(0.0, now - source.t_start))
                self.missed.discard(source.id)
            return
        # Smoke that came through the door from a real fire next door is not a
        # false alarm. A fire on another floor is no excuse at all.
        if not burning and adjacency.get(space, set()) & {s.space for s in lit if s.kind in REAL}:
            return
        cause = burning[0].kind if burning else "none"
        self.false_alarms.append(FalseAlarm(space=space, at=now, cause=cause))

    def summary(self) -> dict:
        """The scorecard as plain data, ready to be sent to the UI."""
        latencies = list(self.detected.values())
        return {
            "detections": len(self.detected),
            "misses": len(self.missed),
            "false_alarms": len(self.false_alarms),
            "mean_latency": round(sum(latencies) / len(latencies), 1) if latencies else None,
            "worst_latency": round(max(latencies), 1) if latencies else None,
            "recent_false_alarms": [
                {"space": f.space, "at": round(f.at, 1), "cause": f.cause}
                for f in self.false_alarms[-5:]
            ],
            **self.timeline.summary(),
        }
