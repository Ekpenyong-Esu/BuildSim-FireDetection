# app/api — REST & SSE Surface

Part 6 of [READING_ORDER.md](../../READING_ORDER.md). Previous: #48 `app/runtime.py`.

How to read (numbers are global across firelab):

- **#49** `models.py` — Pydantic bodies
- **#50** `system.py` — `/healthz`, `/api/state`, rooms, config
- **#51** `clock.py` — `/api/clock`
- **#52** `scenario.py` — `/api/scenario/*`
- **#53** `sensors.py` — `/api/sensors/*`
- **#54** `population.py` — `/api/population`
- **#55** `response.py` — `/api/agent/*`
- **#56** `data.py` — `/api/history`, `/export.csv`
- **#57** `events.py` — `/api/events` (SSE)

`__init__.py` collects these into `ROUTERS`.

Next → #58 [`app/main.py`](../README.md).

See `diagram.mmd`.
