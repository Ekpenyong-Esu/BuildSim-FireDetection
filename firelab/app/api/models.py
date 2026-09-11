"""The request bodies.

Pydantic checks the types, so a bad request is rejected before it ever reaches
the engine.
"""

from pydantic import BaseModel, Field


class ClockBody(BaseModel):
    seconds: float | None = None
    factor: float | None = None
    running: bool | None = None


class IgniteBody(BaseModel):
    space: str
    kind: str = "flaming"
    growth: str = "medium"
    delay: float = 0.0
    peak_kw: float = Field(default=2000.0, gt=0)  # gt=0: a fire with no heat is nonsense


class DeployBody(BaseModel):
    spaces: list[str]
    modalities: list[str] = ["smoke", "co", "temperature"]


class FaultBody(BaseModel):
    device_id: str
    fault: str


class CommandBody(BaseModel):
    kind: str
    space: str
    value: str


class ModeBody(BaseModel):
    auto: bool


class PresetBody(BaseModel):
    preset: str
    space: str


class PopulationBody(BaseModel):
    # A whole mix, so a partial one cannot silently empty the building.
    population: dict[str, int]
