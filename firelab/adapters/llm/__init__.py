"""An LLM as a second detector, behind the same `Detector` protocol as the rule.

The pieces, each with one job:

    verdict.py   what the model answers: a probability, evidence, a reason (pure)
    prompt.py    what the model is asked, from readings only (pure)
    policy.py    when a room is worth asking about again (pure)
    client.py    the one place that talks to the endpoint (OpenAI-compatible)
    detector.py  the Detector: caches verdicts, asks in the background, falls
                 back to the fusion rule whenever it has nothing fresh

The tick loop never waits for the network. `probability()` answers at once from
the last verdict, or from the rule, and only schedules a new question.
"""

from .client import LLMClient, LLMError, LLMSettings
from .detector import LLMDetector
from .policy import RefreshPolicy
from .verdict import Verdict, VerdictError

__all__ = ["LLMClient", "LLMDetector", "LLMError", "LLMSettings", "RefreshPolicy", "Verdict", "VerdictError"]
