"""Why the detector thinks what it thinks, for one room at a time."""


def why(engine, space: str) -> list[dict]:
    """What pushed P(fire) where it is. Asked for one room at a time: sending it
    for all 956 would nearly double every snapshot."""
    features = engine.features.get(space)
    if features is None:
        return []
    return [
        {"name": term.name, "value": round(term.value, 4), "weighted": round(term.weighted, 3)}
        for term in engine.detector.explain(features)
    ]
