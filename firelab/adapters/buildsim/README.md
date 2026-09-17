# adapters/buildsim — Typed HTTP Client

Part 2 of [READING_ORDER.md](../../READING_ORDER.md). Previous: #14 `domain/history.py`.

How to read (numbers are global across firelab):

- **#15** `transport.py` — `Transport` (httpx pool, one error type)
- **#16** `viewer.py` — `ViewerSessions` (imports `transport`)
- **#17** `client.py` — `BuildSim` (imports `transport`+`viewer`)

Next → #18 [`adapters/world_builder.py`](../README.md).

See `diagram.mmd`.
