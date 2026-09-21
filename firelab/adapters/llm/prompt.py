"""What the model is asked about a room. Readings only, never the truth.

Pure: turns a `Features` object into chat messages. Keeping the words here,
away from the network code, means the prompt can be read and changed as text
and tested without an endpoint.
"""

from openai.types.chat import ChatCompletionMessageParam

from ...domain.features import Features

SYSTEM = """You are the fire detector for one room of an office building.
You see only what the room's smoke, CO and temperature sensors reported over
the last two minutes, plus whether neighbouring rooms also see smoke. You
never see the real state of the room.

Decide how likely it is that a real fire is burning in the room, as opposed
to a nuisance. What separates them:
- A flaming fire keeps getting worse: smoke, CO and temperature all rise together.
- A smouldering fire has dense smoke and very high CO but almost no heat.
- Cooking is warm and smoky but its CO stays low, about 25 ppm at most.
- Dust or steam is smoke alone: no CO, no heat, and it fades within minutes.
- A single stuck or drifting sensor disagrees with the others and with the neighbours.
Fewer reporting modalities means less certainty, never more.

Answer with one JSON object and nothing else:
{"p_fire": <number 0..1>,
 "evidence": [{"name": "<short label>", "weight": <number, positive towards fire>}, ...],
 "reason": "<one sentence>"}"""


def messages(features: Features) -> list[ChatCompletionMessageParam]:
    """The chat messages for one room: the fixed instructions, then its readings."""
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": describe(features)},
    ]


def describe(features: Features) -> str:
    """The readings as plain lines, with units, so the model has no guessing to do."""
    lines = [
        f"Room {features.space}.",
        f"Reporting modalities: {features.coverage} of 3.",
        f"Smoke: {features.smoke:.3f} 1/m, rising at {features.smoke_rate:.3f} 1/m per minute.",
        f"CO: {features.co:.0f} ppm.",
        f"Temperature: {features.temperature:.1f} C, {features.temperature_rise:.1f} C above the building baseline.",
        f"CO to smoke ratio: {features.co_smoke_ratio:.0f}.",
        f"Share of monitored neighbours that also see smoke: {features.neighbour_agreement:.2f}.",
    ]
    return "\n".join(lines)
