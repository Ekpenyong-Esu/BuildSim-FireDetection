"""Working out where each level's exits are.

BuildSim's walkable graph stops at the floor slab, so an upper storey cannot
reach a ground-floor door and has to evacuate to its stairwells instead. This
is guesswork about the building, not construction of the world, which is why it
is not in `world_builder.py`.
"""


def derive_exits(floors: dict[str, dict], exits: dict[str, list[str]]) -> dict[str, list[str]]:
    """Fill in exits for levels that have none configured.

    Stairwells line up vertically, so the rooms nearest the known ground-floor
    exits are the right targets.
    """
    known = {level: names for level, names in exits.items() if level in floors}
    if not known:
        return dict(exits)
    # Take the configured ground-floor exits as the anchor points.
    base_level, base_names = next(iter(known.items()))
    base_centers = {r.get("name"): r.get("center") for r in floors[base_level].get("rooms", [])}
    anchors = [base_centers[name] for name in base_names if base_centers.get(name)]

    result = dict(exits)
    for level, payload in floors.items():
        if level in result or not anchors:
            continue  # this level already has exits configured
        rooms = payload.get("rooms", [])
        # Corridors are the likely stairwells; fall back to any room.
        candidates = [r for r in rooms if r.get("type") == "corridor" and r.get("center")] or rooms
        if not candidates:
            continue
        names: list[str] = []
        for ax, ay in anchors:
            # Whichever room sits directly above a ground-floor exit.
            nearest = min(
                candidates,
                key=lambda r: (r["center"][0] - ax) ** 2 + (r["center"][1] - ay) ** 2,
            )
            if nearest["name"] not in names:
                names.append(nearest["name"])
        result[level] = names
    return result
