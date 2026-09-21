"""The API routes used by the browser.

Each route checks the request and passes the work to the shared engine. The
engine and domain files make the simulation decisions.
"""

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
