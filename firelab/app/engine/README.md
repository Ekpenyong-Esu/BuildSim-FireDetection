# app/engine — Orchestration & Tick Loop

Part 4 of [READING_ORDER.md](../../READING_ORDER.md). Previous: #28 `app/evacuation.py`.

How to read (numbers are global across firelab):

- **#29** `constants.py` — `REAL_TICK`, `PUBLISH_EVERY`
- **#30** `streaming.py` — snapshot fan-out to browsers
- **#31** `state.py` — `EngineState` (all mutable state)
- **#32** `core.py` — **overview:** `Engine` tick loop (`truth` → `intelligence` → `actuation` → `publishing`)
- **#33** `building.py` — floor plans → world
- **#34** `session.py` — fresh run: seed, people, clear
- **#35** `truth.py` — zone 1: physics + sensing
- **#36** `intelligence.py` — zone 2: features → P(fire) → state machine
- **#37** `recording.py` — flight recorder
- **#38** `actuation.py` — zone 3: interlocks, then act
- **#39** `publishing.py` — zone 4: writes to BuildSim
- **#40** `devices.py` — install/remove/break sensors
- **#41** `scenario.py` — sources and presets (imports `devices`)

Next → #42 [`app/snapshot/status.py`](../snapshot/README.md).

See `diagram.mmd`.
