"""A short rolling record per space, for the charts and the CSV export.

Stored as flat rows so the whole thing serialises cheaply. Pure: it is told
the time and never samples faster than `SAMPLE_SECONDS` of simulated time.
"""

from dataclasses import dataclass, field

COLUMNS = (
    "t",
    "truth_temperature",
    "truth_smoke",
    "truth_co",
    "read_temperature",
    "read_smoke",
    "read_co",
    "p_fire",
)
MAX_POINTS = 240  # about 20 simulated minutes per room, then the oldest fall off
SAMPLE_SECONDS = 5.0  # simulated seconds between samples


@dataclass
class History:
    """One list of samples per room, oldest first, with a fixed maximum length."""

    tracks: dict[str, list[list[float | None]]] = field(default_factory=dict)  # room key -> rows, one per sample, in COLUMNS order
    _last: float = -1e9  # when the last sample was taken; starts long ago

    def clear(self) -> None:
        """Throw away every recorded sample, on reset."""
        self.tracks.clear()
        self._last = -1e9

    def due(self, now: float) -> bool:
        """Has enough simulated time passed to take another sample?"""
        return now - self._last >= SAMPLE_SECONDS

    def record(self, now: float, rows: dict[str, list[float | None]]) -> None:
        """`rows` maps a space key to the seven values after `t` in COLUMNS."""
        if not self.due(now):
            return  # called every tick, but most ticks are ignored
        self._last = now
        for key, values in rows.items():
            track = self.tracks.setdefault(key, [])
            track.append([round(now, 1), *values])
            del track[:-MAX_POINTS]  # keep only the newest MAX_POINTS samples

    def series(self, space: str) -> list[list[float | None]]:
        """Every sample for one room, or an empty list if it has none."""
        return self.tracks.get(space, [])
