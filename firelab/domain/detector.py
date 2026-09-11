"""P(fire) per space.

The rule and any trained model are interchangeable behind `Detector`, so the
agent never learns which one is installed.
"""

from dataclasses import dataclass
from typing import Protocol

from .features import Features


def _logistic(x: float) -> float:
    """Squash any number into the 0..1 range so it can be read as a probability."""
    from math import exp

    return 1.0 / (1.0 + exp(-x))


@dataclass(frozen=True)
class Contribution:
    """One feature's push towards or away from "this is a fire"."""

    name: str
    value: float  # the raw feature, in its own units
    weighted: float  # what it added to the score


class Detector(Protocol):
    """The contract every detector must satisfy: a score, and the reasons for it.

    Nothing else in the project depends on *how* the score is produced, so the
    rule below can be swapped for a trained model without touching anything.
    """

    name: str  # shown in the UI, so you can tell which detector is installed

    def probability(self, features: Features) -> float:
        """P(fire) for one room, in 0..1, from readings alone."""
        ...

    def explain(self, features: Features) -> list[Contribution]:
        """The terms behind that number, one per piece of evidence.

        Required, not optional: a detector that cannot say why is one nobody can
        sign off on. `probability` must be a function of exactly these terms.
        """
        ...


class FusionRule:
    """Hand-written multi-modal baseline. The model has to beat this."""

    name = "fusion-rule"

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        # How much each piece of evidence counts. `bias` is negative: the room is
        # assumed to be fine until the evidence outweighs it.
        self.weights = weights or {
            "smoke": 3.2,
            "co": 1.8,
            "co_smoke_ratio": 1.6,
            "temperature_rise": 0.55,
            "smoke_rate": 1.4,
            "neighbour_agreement": 0.8,
            "bias": -3.4,
        }

    def explain(self, features: Features) -> list[Contribution]:
        """Score each piece of evidence separately. Their sum is the raw score.

        The UI draws these as bars, so the explanation is the calculation rather
        than a story told about it afterwards.
        """
        w = self.weights
        # The CO/smoke ratio is only meaningful once there is smoke to divide by.
        ratio_gate = min(features.smoke / 0.15, 1.0)
        # Normalised so no single modality can saturate the sum on its own.
        return [
            Contribution("bias", 1.0, w["bias"]),
            Contribution("smoke", features.smoke, w["smoke"] * min(features.smoke, 1.5)),
            # CO on its own, not divided by anything: this is the only term that
            # still speaks when the smoke detector is dead. Cooking peaks at about
            # 25 ppm, so that is where the evidence is taken to start.
            Contribution(
                "co", features.co, w["co"] * min(max(features.co - 25.0, 0.0) / 125.0, 1.0)
            ),
            Contribution(
                "co_smoke_ratio",
                features.co_smoke_ratio,
                w["co_smoke_ratio"] * min(features.co_smoke_ratio / 250.0, 2.5) * ratio_gate,
            ),
            Contribution(
                "temperature_rise",
                features.temperature_rise,
                # Clipped at 60 rather than 40 so a serious fire can be carried by
                # heat alone. Nuisances never get near either number.
                w["temperature_rise"] * min(features.temperature_rise, 60.0) / 10.0,
            ),
            Contribution(
                "smoke_rate",
                features.smoke_rate,
                w["smoke_rate"] * min(max(features.smoke_rate, 0.0), 1.0),
            ),
            Contribution(
                "neighbour_agreement",
                features.neighbour_agreement,
                w["neighbour_agreement"] * features.neighbour_agreement,
            ),
        ]

    def probability(self, features: Features) -> float:
        """Add up the contributions and turn the total into a 0..1 probability."""
        if features.coverage == 0:
            return 0.0  # no working sensor: no opinion, not a low probability
        score = sum(term.weighted for term in self.explain(features))
        # Fewer working sensors means less confidence, so the score is held back.
        # With only one modality it can never reach the confirm threshold.
        confidence = min(features.coverage, 3) / 3.0
        return _logistic(score) * (0.55 + 0.45 * confidence)
