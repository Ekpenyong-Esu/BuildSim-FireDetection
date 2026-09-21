"""Choose the detector the engine runs, from the config.

One place decides which `Detector` is installed, so the engine's state never
has to know how an LLM client is built or where its secrets come from. The
rule is the default and the safety net: if the LLM is asked for but not
configured, the rule is installed and the journal says why.
"""

from collections.abc import Callable

from ..adapters.llm import LLMClient, LLMDetector, LLMSettings, RefreshPolicy
from ..adapters.llm.client import LLMConfigError
from ..domain.detector import Detector, FusionRule
from .config import Config

KINDS = ("fusion-rule", "llm")


def make_detector(config: Config, clock: Callable[[], float], log: Callable[[str, str], None]) -> Detector:
    """The detector the config asks for, ready to install.

    `clock` returns simulated seconds; `log` writes a journal line. Both are
    handed to the LLM detector so it owns neither a clock nor a logger of its own.
    """
    settings = config.detector
    if settings.kind != "llm":
        return FusionRule()
    try:
        endpoint = LLMSettings.from_env()
    except LLMConfigError as exc:
        log("error", f"LLM detector not configured ({exc}); using the fusion rule")
        return FusionRule()
    log("info", f"LLM detector: {endpoint.model} at {endpoint.base_url}")
    return LLMDetector(
        completer=LLMClient(endpoint, timeout=settings.timeout_seconds),
        clock=clock,
        fallback=FusionRule(),
        policy=RefreshPolicy(every=settings.refresh_seconds, max_age=settings.max_age_seconds),
        log=log,
        max_concurrency=settings.max_concurrency,
    )
