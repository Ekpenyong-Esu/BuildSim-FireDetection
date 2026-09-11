"""How each kind of person is getting on during the evacuation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...domain import roles as roles_mod

if TYPE_CHECKING:
    from ..engine.state import EngineState


def population(engine: EngineState) -> list[dict]:
    """How each role is getting on. Visitors are expected to lag the students."""
    rows = []
    for role in roles_mod.ROLES:
        people = [o for o in engine.occupants if o.role == role.key]
        if not people:
            continue
        rows.append(
            {
                "key": role.key,
                "label": role.label,
                "note": role.note,
                "speed": role.speed,
                "total": len(people),
                "safe": sum(1 for o in people if o.safe),
                "evacuating": sum(1 for o in people if o.status == "evacuating"),
                "stranded": sum(1 for o in people if o.status == "no route"),
            }
        )
    return rows
