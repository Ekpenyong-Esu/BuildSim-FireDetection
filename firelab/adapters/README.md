# adapters — I/O Bridges

Part 2 of [READING_ORDER.md](../READING_ORDER.md). Previous: #14 `domain/history.py`.

How to read (numbers are global across firelab):

- **#15–17** `buildsim/` — typed HTTP client — see [buildsim/README.md](buildsim/README.md)
- **#18** `world_builder.py` — floor plans → `World`
- **#19** `walkways.py` — escape-route search (imports `world_builder`)
- **#20–25** `publisher/` — state → BuildSim payloads — see [publisher/README.md](publisher/README.md)

Next → #26 [`app/config.py`](../app/README.md).

See `diagram.mmd`.
