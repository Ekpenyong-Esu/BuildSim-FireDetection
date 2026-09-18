"""Whether a room is still survivable, and how much dose people have taken.

Pure: standard library only. The criteria are the escape thresholds from
ISO 13571 — they mark the point where conditions stop people getting out, which
is well before the point where conditions kill.
"""

from dataclasses import dataclass

TEMP_LIMIT = 60.0  # degrees C: above this, convected heat impairs escape
SMOKE_LIMIT = 0.30  # 1/m optical density, roughly 10 m visibility
FED_LIMIT = 0.3  # fractional effective dose; 1.0 incapacitates the average adult,
# and the margin is there because a lecture theatre is not full of average adults.

VISIBILITY_K = 3.0  # reflecting signs; light-emitting ones would be 8


def visibility(smoke: float) -> float | None:
    """How far you can see, in metres. None means the air is still clear."""
    return VISIBILITY_K / smoke if smoke > 1e-6 else None


def fed_increment(co_ppm: float, dt: float) -> float:
    """The fraction of an incapacitating CO dose taken in `dt` seconds.

    ISO 13571's exponent is slightly above 1, so a short exposure to a lot of CO
    hurts more than a long exposure to a little.
    """
    if co_ppm <= 0.0:
        return 0.0
    return (co_ppm**1.036) / 35000.0 * (dt / 60.0)


@dataclass(frozen=True)
class Verdict:
    """Whether a space is escapable, and the first criterion that failed."""

    tenable: bool  # True: a person could still escape through this room
    reason: str  # "" when tenable


def assess(temperature: float, smoke: float) -> Verdict:
    """Judge one room on the conditions a person standing in it would meet.

    Heat is checked before smoke because it is the one that stops you outright.
    """
    if temperature >= TEMP_LIMIT:
        return Verdict(False, f"{temperature:.0f} °C")
    if smoke >= SMOKE_LIMIT:
        return Verdict(False, f"visibility {visibility(smoke):.0f} m")
    return Verdict(True, "")
