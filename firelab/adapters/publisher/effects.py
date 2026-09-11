"""Particle effects for the 3D scene: what is physically happening."""

from ...domain.world import World

SMOKE_THRESHOLD = 0.08  # below this there is nothing worth drawing
MAX_SMOKE_EFFECTS = 40  # particle systems are expensive in the viewer


def effects(world: World, burning: set[str]) -> list[dict]:
    """Fire, sprinkler and smoke particle effects for the 3D scene."""
    payload: list[dict] = []
    for key in burning:
        space = world.spaces[key]
        # Hotter fires are drawn bigger, clamped so a small one is still visible.
        intensity = min(1.0, max(0.2, (space.temperature - 20.0) / 120.0))
        payload.append(
            {
                "id": f"fire-{space.name}",
                "type": "fire",
                "label": f"Fire in {space.name}",
                "level": space.level,
                "room": space.name,
                "radius": 6,
                "height": 12,
                "intensity": round(intensity, 2),
            }
        )

    for space in world.spaces.values():
        if space.sprinkler:
            payload.append(
                {
                    "id": f"sprinkler-{space.name}",
                    "type": "sprinkler",
                    "level": space.level,
                    "room": space.name,
                    "radius": 5,
                    "height": 10,
                    "intensity": 0.9,
                }
            )

    smoky = sorted(
        (s for s in world.spaces.values() if s.smoke > SMOKE_THRESHOLD),
        key=lambda s: s.smoke,
        reverse=True,
    )
    # Only the smokiest rooms get an effect, or the viewer's frame rate collapses.
    for space in smoky[:MAX_SMOKE_EFFECTS]:
        payload.append(
            {
                "id": f"smoke-{space.name}",
                "type": "smoke",
                "level": space.level,
                "room": space.name,
                "radius": 8,
                "height": 16,
                "intensity": round(min(1.0, space.smoke), 2),
            }
        )
    return payload
