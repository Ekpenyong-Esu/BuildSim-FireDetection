"""The evacuation clock: ignition, alarm, building empty.

Detection latency is only half the story. RSET — how long people actually
needed to get out — is a different question from whether the alarm was
correct, so it is kept apart from the accuracy tally in `scoring.py`.
"""

from dataclasses import dataclass


@dataclass
class Timeline:
    """The three milestones of a run, and the gaps between them."""

    ignition_at: float | None = None  # when the first real fire lit
    alarm_at: float | None = None  # when the first room reached CONFIRMED
    cleared_at: float | None = None  # when the last person got out
    moved: bool = False  # somebody has actually started walking

    def clear(self) -> None:
        """Start a fresh run with the clock unstarted."""
        self.ignition_at = None
        self.alarm_at = None
        self.cleared_at = None
        self.moved = False

    def note_alarm(self, now: float, alarming: bool) -> None:
        """The first alarm of the run starts the response clock."""
        if alarming and self.alarm_at is None:
            self.alarm_at = now

    def note_ignition(self, lit: list[float]) -> None:
        """The earliest real fire to light is what RSET is measured from."""
        if lit and self.ignition_at is None:
            self.ignition_at = min(lit)

    def note_evacuation(self, now: float, evacuating: int, inside: int) -> None:
        """The building is only "cleared" if it was ever evacuating.

        An empty building nobody had to leave is not an evacuation time.
        """
        self.moved = self.moved or evacuating > 0
        if self.moved and inside == 0 and self.cleared_at is None:
            self.cleared_at = now

    def summary(self) -> dict:
        """The timing half of the scorecard."""
        return {
            "alarm_delay": _gap(self.ignition_at, self.alarm_at),
            "rset": _gap(self.ignition_at, self.cleared_at),
            "rset_from_alarm": _gap(self.alarm_at, self.cleared_at),
            "clearing": self.moved and self.cleared_at is None,
        }


def _gap(start: float | None, end: float | None) -> float | None:
    """Seconds between two milestones, or None while either is still ahead."""
    if start is None or end is None:
        return None
    return round(max(0.0, end - start), 1)
