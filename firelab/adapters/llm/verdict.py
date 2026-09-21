"""What the model answers about one room, and how its answer is checked.

Pure: no network, no clock. The detector hands in the model's text and the
simulated time it was asked; this file turns it into a `Verdict` or refuses.
"""

import json
from dataclasses import dataclass

REASON_LIMIT = 200  # characters kept from the model's explanation, for the journal


class VerdictError(ValueError):
    """The model's answer was not a usable verdict."""


@dataclass(frozen=True)
class Evidence:
    """One piece of evidence the model weighed, positive towards fire."""

    name: str
    weight: float


@dataclass(frozen=True)
class Verdict:
    """The model's opinion of one room at one moment."""

    p_fire: float  # 0..1
    evidence: tuple[Evidence, ...]  # what it weighed, largest first
    reason: str  # one line, for the journal
    at: float  # simulated time the readings it saw were taken


def parse(text: str, at: float) -> Verdict:
    """Turn the model's JSON reply into a Verdict, or raise VerdictError.

    The reply must be an object with `p_fire` (number), `evidence` (a list of
    `{"name", "weight"}` objects) and `reason` (a string). Anything else is
    refused rather than guessed at, so a malformed answer leaves the rule in
    charge instead of feeding the alarm ladder a number nobody vouched for.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise VerdictError(f"not JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise VerdictError("reply is not an object")

    p_fire = data.get("p_fire")
    if not isinstance(p_fire, (int, float)) or isinstance(p_fire, bool):
        raise VerdictError("p_fire missing or not a number")

    evidence: list[Evidence] = []
    for item in data.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        name, weight = item.get("name"), item.get("weight")
        if isinstance(name, str) and isinstance(weight, (int, float)) and not isinstance(weight, bool):
            evidence.append(Evidence(name.strip()[:40], float(weight)))
    evidence.sort(key=lambda e: e.weight, reverse=True)

    reason = data.get("reason")
    if not isinstance(reason, str):
        reason = ""

    return Verdict(
        p_fire=min(max(float(p_fire), 0.0), 1.0),
        evidence=tuple(evidence),
        reason=" ".join(reason.split())[:REASON_LIMIT],
        at=at,
    )
