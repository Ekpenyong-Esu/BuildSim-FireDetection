"""Who is in the building."""

from fastapi import APIRouter, HTTPException

from ...domain.roles import ROLE_BY_KEY, ROLES
from ..engine import session
from ..runtime import engine
from .models import PopulationBody

# The viewer stops drawing individual markers long before this; it is here so an
# untrusted request cannot ask for a million people.
MAX_OCCUPANTS = 2000

router = APIRouter()


@router.get("/api/roles")
async def list_roles() -> list[dict]:
    """The kinds of people who can be in the building."""
    return [{"key": r.key, "label": r.label, "speed": r.speed, "note": r.note} for r in ROLES]


@router.put("/api/population")
async def put_population(body: PopulationBody) -> dict:
    """Set how many of each role there are and scatter them again."""
    unknown = set(body.population) - set(ROLE_BY_KEY)
    if unknown:
        raise HTTPException(status_code=400, detail=f"unknown roles: {', '.join(sorted(unknown))}")
    if any(count < 0 for count in body.population.values()):
        raise HTTPException(status_code=400, detail="counts cannot be negative")
    total = sum(body.population.values())
    if total > MAX_OCCUPANTS:
        raise HTTPException(status_code=400, detail=f"at most {MAX_OCCUPANTS} people")
    engine.config.population = {key: int(v) for key, v in body.population.items()}
    session.place_occupants(engine, engine.config.population)
    engine.log("info", f"population set to {total} people")
    return engine.config.to_dict()
