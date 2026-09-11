"""Heat maps painted on the floor plans: three truths and one belief."""

from ...domain.world import World

# Labels shown in the viewer's legend, so nobody confuses what is real with
# what the system merely thinks.
TRUTH = "simulation truth"
BELIEF = "decision-service estimate"


def room_layers(world: World, probabilities: dict[str, float]) -> list[dict]:
    """Four heat maps painted on the floors: three truths and one belief.

    Putting them side by side is the point of the whole project: you can see
    exactly where the detector's picture differs from reality.
    """
    return [
        {
            "id": "temperature",
            "label": "True room temperature",
            "unit": "°C",
            "source": TRUTH,
            "minimum": 18,
            "maximum": 120,
            "opacity": 0.75,
            "palette": ["#2563eb", "#22c55e", "#facc15", "#dc2626"],
            "values": {key: round(s.temperature, 2) for key, s in world.spaces.items()},
        },
        {
            "id": "smoke",
            "label": "True smoke obscuration",
            "unit": "1/m",
            "source": TRUTH,
            "minimum": 0,
            "maximum": 1.5,
            "opacity": 0.75,
            "palette": ["#0f172a", "#475569", "#cbd5f5", "#f8fafc"],
            "values": {key: round(s.smoke, 4) for key, s in world.spaces.items()},
        },
        {
            "id": "co",
            "label": "True CO concentration",
            "unit": "ppm",
            "source": TRUTH,
            "minimum": 0,
            "maximum": 1200,
            "opacity": 0.75,
            "palette": ["#22c55e", "#facc15", "#f97316", "#dc2626"],
            "values": {key: round(s.co, 1) for key, s in world.spaces.items()},
        },
        {
            "id": "p_fire",
            "label": "Detector P(fire)",
            "unit": "",
            "source": BELIEF,
            "minimum": 0,
            "maximum": 1,
            "opacity": 0.8,
            "palette": ["#1e293b", "#0ea5e9", "#f59e0b", "#dc2626"],
            "values": {key: round(value, 3) for key, value in probabilities.items()},
        },
    ]
