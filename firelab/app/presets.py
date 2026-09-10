"""One-click scenarios. A preset is a template; the room comes from the UI."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Preset:
    """A ready-made scenario. Pick one, pick a room, and press start."""

    id: str
    name: str
    description: str
    kind: str  # what to ignite: "flaming", "smouldering", "cooking", "dust", or "" for nothing
    growth: str = "medium"
    peak_kw: float = 2000.0
    delay: float = 0.0  # simulated seconds to wait before igniting
    fault: str = "none"  # applied to one device in the room, to make life hard


# The six scenarios in the UI. The first two should be caught, the middle two
# should never raise an alarm, and the last two are the interesting failures.
PRESETS = (
    Preset(
        id="office-fire",
        name="Office fire",
        description="Fast flaming fire. The easy case — everything corroborates.",
        kind="flaming",
        growth="fast",
    ),
    Preset(
        id="overnight-smoulder",
        name="Overnight smoulder",
        description="Barely any heat, dense smoke, high CO. Only CO catches it.",
        kind="smouldering",
    ),
    Preset(
        id="kitchen-cooking",
        name="Kitchen cooking",
        description="The classic nuisance. Any alarm here is a false alarm.",
        kind="cooking",
    ),
    Preset(
        id="dust-storm",
        name="Dust storm",
        description="Smoke without fire: no heat, no CO.",
        kind="dust",
    ),
    Preset(
        id="blind-spot",
        name="Fire with a dead detector",
        description="Flaming fire while the smoke detector is dead — CO and heat must carry it.",
        kind="flaming",
        growth="fast",
        fault="dead",
    ),
    Preset(
        id="drifting-sensor",
        name="Drifting sensor, no fire",
        description="Nothing is burning; one detector drifts upwards. Does it alarm?",
        kind="",
        fault="drift",
    ),
)

BY_ID = {preset.id: preset for preset in PRESETS}  # for quick lookup by the API


def catalogue() -> list[dict]:
    """All presets as plain data, for the UI to list."""
    return [asdict(preset) for preset in PRESETS]
