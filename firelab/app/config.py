"""Runtime configuration. Everything here is editable from the UI."""

from dataclasses import asdict, dataclass, field

from ..domain.roles import DEFAULT_POPULATION


@dataclass
class SensorConfig:
    """How good the sensors are. Turn `noise_scale` up to make life harder."""

    noise_scale: float = 1.0  # 0 = perfect sensors, 3 = badly behaved ones
    interval: float = 5.0  # simulated seconds between readings
    modalities: list[str] = field(default_factory=lambda: ["smoke", "co", "temperature"])  # the full set; unused today, the panel sends its own list on deploy


@dataclass
class ResponseConfig:
    """When the agent acts, and whether it is allowed to act on its own."""

    auto: bool = True  # False means a human has to approve every command
    # The alarm ladder's rungs; the same fields as domain.agent.Thresholds.
    investigate: float = 0.35  # P(fire) at which a room is worth watching
    pre_alarm: float = 0.55  # P(fire) for PRE_ALARM, once held for dwell_pre_alarm
    confirm: float = 0.75  # P(fire) for CONFIRMED, once PRE_ALARM has lasted dwell_confirm
    clear: float = 0.25  # P(fire) at or below which the alarm stands down, after dwell_clear
    dwell_pre_alarm: float = 20.0  # simulated seconds
    dwell_confirm: float = 25.0
    dwell_clear: float = 90.0


@dataclass
class Config:
    """Every knob in one place. The UI edits this and the engine re-reads it."""

    buildsim_url: str = "http://127.0.0.1:9090"  # where BuildSim is listening
    levels: list[str] = field(default_factory=lambda: ["level0", "level1", "level2"])  # the floors to load, ground floor first
    factor: float = 1.0  # simulated seconds per real second
    step_seconds: float = 1.0  # simulated seconds per physics step
    seed: int = 1  # fix the randomness, so a run can be repeated exactly
    population: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_POPULATION))  # role key -> how many
    walking_speed: float = 1.3  # m/s, before each role's own factor
    sensors: SensorConfig = field(default_factory=SensorConfig)  # applies to sensors deployed after a change
    response: ResponseConfig = field(default_factory=ResponseConfig)  # re-read by the agent every tick
    # Real doors to the outside. Only the ground floor has any, and only these
    # count as being out of the building: upper storeys are routed down the
    # stairs to one of them rather than to a landing that merely looks like an
    # exit.
    exits: dict[str, list[str]] = field(
        default_factory=lambda: {
            "level0": ["A1016", "A1123", "A105", "A10", "A1000A", "A1000E", "A170"]
        }
    )

    def to_dict(self) -> dict:
        """The whole config as plain JSON-friendly data."""
        return asdict(self)

    def apply(self, patch: dict) -> None:
        """Merge a partial update from the UI, ignoring any unknown keys.

        `hasattr` is the guard: it means a typo or a stale field in the request
        is quietly dropped rather than creating a bogus setting.
        """
        for key, value in patch.items():
            if key == "sensors" and isinstance(value, dict):
                for name, item in value.items():
                    if hasattr(self.sensors, name):
                        setattr(self.sensors, name, item)
            elif key == "response" and isinstance(value, dict):
                for name, item in value.items():
                    if hasattr(self.response, name):
                        setattr(self.response, name, item)
            elif hasattr(self, key):
                setattr(self, key, value)
