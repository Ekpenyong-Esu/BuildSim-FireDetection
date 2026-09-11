"""The REST and SSE surface, one router per thing you can ask the engine to do."""

from . import clock, data, events, population, response, scenario, sensors, system

ROUTERS = [
    system.router,
    events.router,
    clock.router,
    scenario.router,
    population.router,
    sensors.router,
    response.router,
    data.router,
]

__all__ = ["ROUTERS"]
