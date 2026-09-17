# internal/sim — Movement Simulation

How to read:

1. `config.go` / `rooms.go` / `graph.go` — standalone
2. `plan.go` — daily plans (imports `graph`)
3. `sim.go` — `State`/`Person` (imports `config`+`plan`+`graph`+`rooms`)

See `diagram.mmd`.
