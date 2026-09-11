"""Shared fixtures: a two-room building with a doorway between them."""

from firelab.domain import world as world_mod


def make_world() -> world_mod.World:
    world = world_mod.World()
    for name in ("A1", "A2"):
        world.spaces[f"level0/{name}"] = world_mod.Space(
            key=f"level0/{name}",
            level="level0",
            name=name,
            kind="room",
            area_m2=25.0,
            center=(0.0, 0.0),
        )
    world.couplings.append(world_mod.Coupling(a="level0/A1", b="level0/A2", conductance=0.5))
    return world
