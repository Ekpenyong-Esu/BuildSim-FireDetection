# pkg/server/handlers — One File Per Route

How to read:

1. `building.go` — `GET /api/building`
2. `graph.go` — `GET /api/graph`, `POST /api/route`
3. `sensor.go` / `actuator.go` — device I/O
4. `occupancy.go` / `session.go` / `equipment.go` / `visualization.go` — state
5. `editor.go` / `coverage.go` / `notify.go` / `validation.go` — extras

All registered by `server.go`. See `diagram.mmd`.
