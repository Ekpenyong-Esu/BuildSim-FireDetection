"""The request bodies.

Pydantic checks the types, so a bad request is rejected before it ever reaches
the engine. Each class is the contract for exactly one endpoint, named in its
docstring, so this file reads as the whole write surface of the API on one page.
"""

from pydantic import BaseModel, Field


class ClockBody(BaseModel):
    """`POST /api/clock` — play, pause, jump in time, or change the speed.

    Every field is optional and only the ones sent are applied, so the UI can
    nudge the speed without also having to say where the clock is.
    """

    seconds: float | None = None  # jump to this simulated time
    factor: float | None = None  # simulated seconds per real second
    running: bool | None = None  # play or pause


class IgniteBody(BaseModel):
    """`POST /api/scenario/ignite` — light one source in one room."""

    space: str  # canonical "<level>/<name>" key
    kind: str = "flaming"  # one of domain.sources.KINDS
    growth: str = "medium"  # t-squared growth rate: slow..ultrafast
    delay: float = 0.0  # simulated seconds to wait before it lights
    peak_kw: float = Field(default=2000.0, gt=0)  # gt=0: a fire with no heat is nonsense


class DeployBody(BaseModel):
    """`POST /api/sensors/deploy` and `/undeploy` — install or remove detectors.

    Deploying is what makes a room monitored at all: an undeployed room has no
    readings, no agent and no opinion, so it cannot alarm however hard it burns.
    """

    spaces: list[str]
    modalities: list[str] = ["smoke", "co", "temperature"]  # undeploy ignores this


class FaultBody(BaseModel):
    """`POST /api/sensors/fault` — break one detector on purpose.

    The point of the whole project: see whether the rest of the system copes.
    """

    device_id: str
    fault: str  # one of domain.sensing.FAULTS


class CommandBody(BaseModel):
    """`POST /api/actuators/command` — a human-issued actuator command.

    It still passes the same interlocks the agent's commands do; clicking is not
    a privileged path.
    """

    kind: str  # "sprinkler" | "fire_door" | "evacuate"
    space: str
    value: str  # what to set it to, e.g. "on" / "closed" / "start"


class ModeBody(BaseModel):
    """`POST /api/agent/mode` — autonomous response on or off.

    False is supervised mode: the agent still decides, but its commands are
    dropped rather than carried out until a human issues them.
    """

    auto: bool


class PresetBody(BaseModel):
    """`POST /api/scenario/preset` — run one of the six one-click scenarios."""

    preset: str  # an id from app.presets.BY_ID
    space: str


class PopulationBody(BaseModel):
    """`PUT /api/population` — re-scatter the people through the building."""

    # A whole mix, so a partial one cannot silently empty the building.
    population: dict[str, int]
