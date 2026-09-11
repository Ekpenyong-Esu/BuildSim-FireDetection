"""What the system believes: room outlines and the alert banner."""

from ...domain.world import World

STATE_COLOURS = {
    # state -> (colour, opacity). Redder and more solid means more serious.
    "CONFIRMED": ("#dc2626", 0.85),
    "SUPPRESSED": ("#dc2626", 0.6),
    "PRE_ALARM": ("#f97316", 0.7),
    "INVESTIGATING": ("#facc15", 0.5),
    "CLEARING": ("#22c55e", 0.4),
}

SEVERITY = {
    # How loudly the viewer should announce each state.
    "INVESTIGATING": "info",
    "PRE_ALARM": "warning",
    "CONFIRMED": "critical",
    "SUPPRESSED": "critical",
    "CLEARING": "info",
}


def highlights(world: World, states: dict[str, str]) -> list[dict]:
    """Outline every room the agent is currently worried about."""
    payload = []
    for key, state in states.items():
        space = world.spaces.get(key)
        colour = STATE_COLOURS.get(state)
        if space is None or colour is None:
            continue  # NORMAL rooms have no colour, so they are simply skipped
        payload.append(
            {
                "level": space.level,
                "room": space.name,
                "color": colour[0],
                "opacity": colour[1],
            }
        )
    return payload


def alerts(world: World, states: dict[str, str], probabilities: dict[str, float]) -> list[dict]:
    """One readable message per room in an alarm state."""
    payload = []
    for key, state in states.items():
        space = world.spaces.get(key)
        severity = SEVERITY.get(state)
        if space is None or severity is None:
            continue
        payload.append(
            {
                "id": f"alarm-{space.level}-{space.name}",
                "severity": severity,
                "title": f"{state.replace('_', ' ').title()} in {space.name}",
                "message": f"P(fire) {probabilities.get(key, 0.0):.0%}"
                + (", sprinkler active" if space.sprinkler else ""),
                "level": space.level,
                "room": space.name,
            }
        )
    return payload[:100]  # a wall of alerts helps nobody
