"""Readings -> feature vectors. Nothing here may see the truth."""

from dataclasses import dataclass, field

WINDOW_SECONDS = 120.0  # how far back the detector is allowed to look


@dataclass
class Features:
    """The summary of one room that the detector is given. Readings only."""

    space: str  # key of the room these describe
    smoke: float = 0.0  # latest smoke reading, 1/m
    co: float = 0.0  # latest CO reading, ppm
    temperature: float = 20.0  # latest temperature reading, °C (20 if none yet)
    smoke_rate: float = 0.0  # per minute
    temperature_rise: float = 0.0  # above the building baseline
    co_smoke_ratio: float = 0.0  # co / smoke; high for a smoulder, low for dust or steam
    neighbour_agreement: float = 0.0  # 0..1: share of monitored neighbours that also see smoke
    coverage: int = 0  # how many modalities reported

    def vector(self) -> list[float]:
        """The same features as a plain list, the shape a model would expect."""
        return [
            self.smoke,
            self.co,
            self.temperature_rise,
            self.smoke_rate,
            self.co_smoke_ratio,
            self.neighbour_agreement,
        ]


@dataclass
class Window:
    """Per-space sliding window over device readings."""

    space: str  # key of the room these readings came from
    series: dict[str, list[tuple[float, float]]] = field(default_factory=dict)  # modality -> [(t, value)], last 120 s

    def add(self, modality: str, now: float, value: float) -> None:
        """Store one new reading and forget anything older than the window."""
        points = self.series.setdefault(modality, [])
        points.append((now, value))
        cutoff = now - WINDOW_SECONDS
        while points and points[0][0] < cutoff:
            points.pop(0)

    def latest(self, modality: str, default: float = 0.0) -> float:
        """The most recent reading, or `default` if this sensor has said nothing."""
        points = self.series.get(modality)
        return points[-1][1] if points else default

    def rate_per_minute(self, modality: str) -> float:
        """How fast the value is changing: oldest to newest, scaled to a minute."""
        points = self.series.get(modality) or []
        if len(points) < 2:
            return 0.0  # need two points to measure a change
        (t0, v0), (t1, v1) = points[0], points[-1]
        span = t1 - t0
        return 0.0 if span <= 0 else (v1 - v0) / span * 60.0


def extract(window: Window, neighbour_smoke: list[float], baseline: float = 20.0) -> Features:
    """Turn two minutes of readings into the handful of numbers the detector uses.

    Note the arguments: a window of readings and the neighbours' smoke levels.
    The true state of the room is deliberately not available here.
    """
    smoke = window.latest("smoke")
    co = window.latest("co")
    temperature = window.latest("temperature", baseline)

    # Real smoke spreads next door; a faulty sensor is alone in what it sees.
    agreement = 0.0
    if neighbour_smoke:
        raised = sum(1 for value in neighbour_smoke if value > 0.05)
        agreement = raised / len(neighbour_smoke)

    return Features(
        space=window.space,
        smoke=smoke,
        co=co,
        temperature=temperature,
        smoke_rate=window.rate_per_minute("smoke"),
        temperature_rise=max(0.0, temperature - baseline),
        # Below a little smoke the ratio is meaningless, so force it to zero.
        co_smoke_ratio=co / smoke if smoke > 0.05 else 0.0,
        neighbour_agreement=agreement,
        # How many of the three sensors are working: how much to trust the rest.
        coverage=len([m for m in ("smoke", "co", "temperature") if window.series.get(m)]),
    )
