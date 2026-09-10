"""Grade the system against the ground truth the sources carry.

Every source knows whether it is a real fire or a nuisance, so the run can be
scored while it happens: how fast real fires were caught, which nuisances the
system fell for, and which fires it missed. Pure: it is told the time.
"""

from dataclasses import dataclass, field

from .sources import Source

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
    _alarming: set[str] = field(default_factory=set)  # rooms alarming last tick

    # The evacuation timeline. Detection latency is only half the story; what
    # matters is whether the warning came early enough to empty the building.
    ignition_at: float | None = None
    alarm_at: float | None = None
    cleared_at: float | None = None
    _moved: bool = False  # somebody has actually started walking

    def clear(self) -> None:
        """Start a fresh run with an empty scorecard."""
        self.detected.clear()
        self.missed.clear()
        self.false_alarms.clear()
        self._alarming.clear()
        self.ignition_at = None
        self.alarm_at = None
        self.cleared_at = None
        self._moved = False

    def update(
        self,
        now: float,
        sources: list[Source],
        states: dict[str, str],
        evacuating: int = 0,
        inside: int = 0,
    ) -> None:
        """Mark the system's homework for this tick."""
        # Compare with last tick so each alarm is only judged once, when raised.
        alarming = {key for key, state in states.items() if state in ALARM_STATES}
        for space in alarming - self._alarming:  # a newly raised alarm
            self._score_alarm(space, now, sources)
        self._alarming = alarming
        if alarming and self.alarm_at is None:
            self.alarm_at = now

        lit = [s.t_start for s in sources if s.kind in REAL and s.t_start <= now]
        if lit and self.ignition_at is None:
            self.ignition_at = min(lit)

        # The building is only "cleared" if it was ever evacuating; an empty
        # building that nobody had to leave is not an evacuation time.
        self._moved = self._moved or evacuating > 0
        if self._moved and inside == 0 and self.cleared_at is None:
            self.cleared_at = now

        # A real fire nobody has confirmed after five minutes counts as missed.
        for source in sources:
            if source.kind not in REAL or source.id in self.detected:
                continue
            if now - source.t_start > MISS_AFTER:
                self.missed.add(source.id)

    def _score_alarm(self, space: str, now: float, sources: list[Source]) -> None:
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
        if not burning and any(s.kind in REAL for s in lit):
            return  # smoke that spread from a real fire; the alarm is correct
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
            "alarm_delay": _gap(self.ignition_at, self.alarm_at),
            "rset": _gap(self.ignition_at, self.cleared_at),
            "rset_from_alarm": _gap(self.alarm_at, self.cleared_at),
            "clearing": self._moved and self.cleared_at is None,
            "recent_false_alarms": [
                {"space": f.space, "at": round(f.at, 1), "cause": f.cause}
                for f in self.false_alarms[-5:]
            ],
        }


def _gap(start: float | None, end: float | None) -> float | None:
    """Seconds between two milestones, or None while either is still ahead."""
    if start is None or end is None:
        return None
    return round(max(0.0, end - start), 1)
