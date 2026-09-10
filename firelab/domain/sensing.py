"""The boundary where truth becomes observation.

Each device applies its own corruption chain:

    lag -> calibration bias -> noise -> quantisation -> clamp -> fault

Pure: standard library only. `random.Random` is passed in so a run is
reproducible from a seed.
"""

from dataclasses import dataclass, field
from random import Random

from .physics import approach

MODALITIES = ("smoke", "co", "temperature")

FAULTS = ("none", "stuck", "dropout", "drift", "dead")

# Per-modality imperfections. tau = how sluggish, bias = a constant offset,
# noise = random jitter, quantum = the smallest step it can report, lo/hi = range.
# Temperature is the slowest because a real heat detector has thermal mass.
DEFAULTS = {
    #            tau   bias  noise  quantum  lo      hi
    "smoke": (12.0, 0.0, 0.010, 0.005, 0.0, 3.0),
    "co": (25.0, 0.0, 3.0, 1.0, 0.0, 2000.0),
    "temperature": (30.0, 0.0, 0.15, 0.1, -20.0, 250.0),
}


@dataclass
class Device:
    """One emulated detector living in one space."""

    id: str
    space: str
    modality: str
    tau: float
    bias: float
    noise: float
    quantum: float
    low: float
    high: float
    interval: float = 5.0  # seconds between readings
    fault: str = "none"
    internal: float = 0.0  # what the sensing element currently feels
    reading: float | None = None  # the last value it actually reported
    drift: float = 0.0  # accumulated error, only grows when faulty
    next_sample: float = 0.0
    history: list[tuple[float, float]] = field(default_factory=list)

    @classmethod
    def create(cls, device_id: str, space: str, modality: str, **overrides) -> "Device":
        """Build a device with the standard characteristics for its modality."""
        tau, bias, noise, quantum, low, high = DEFAULTS[modality]
        device = cls(
            id=device_id,
            space=space,
            modality=modality,
            tau=tau,
            bias=bias,
            noise=noise,
            quantum=quantum,
            low=low,
            high=high,
        )
        for name, value in overrides.items():
            if hasattr(device, name):
                setattr(device, name, value)
        # A thermometer starts at room temperature; the others start at zero.
        device.internal = 20.0 if modality == "temperature" else 0.0
        return device


def sample(device: Device, truth: float, now: float, dt: float, rng: Random) -> float | None:
    """Advance the device and return a new reading, or None between samples.

    This is the only place the true value is turned into an observation, and it
    is where every one of the system's blind spots comes from.
    """
    # The element always tracks reality, but lags behind it.
    device.internal = approach(device.internal, truth, max(device.tau, 1e-3), dt)

    # Real detectors report every few seconds, not continuously.
    if now < device.next_sample:
        return None
    device.next_sample = now + max(device.interval, 1.0)

    if device.fault == "dead":
        device.reading = None
        return None  # says nothing, ever
    if device.fault == "dropout" and rng.random() < 0.4:
        return None  # skips this reading at random
    if device.fault == "stuck":
        # Repeats its last value forever: looks alive, reports nothing new.
        value = device.reading if device.reading is not None else device.internal
        device.reading = value
        _remember(device, now, value)
        return value
    if device.fault == "drift":
        # Wanders upward a little more each reading. The classic false alarm.
        device.drift += 0.02 * (device.high - device.low) / 600.0 * device.interval

    # The healthy path: offset, then jitter, then rounding, then the sensor range.
    value = device.internal + device.bias + device.drift
    value += rng.gauss(0.0, device.noise)
    if device.quantum > 0:
        value = round(value / device.quantum) * device.quantum
    value = min(max(value, device.low), device.high)

    device.reading = value
    _remember(device, now, value)
    return value


def _remember(device: Device, now: float, value: float) -> None:
    """Keep the recent readings, which is what the feature window looks at."""
    device.history.append((now, value))
    if len(device.history) > 240:
        del device.history[: len(device.history) - 240]
