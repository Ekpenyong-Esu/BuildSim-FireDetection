# firelab — Reading Order

One numbered path through the whole repository. Read the files top to bottom:
each file only depends on files with a smaller number, so nothing is used before
you have seen it. The one deliberate exception is **#32 `engine/core.py`**, read
early as an overview of the tick loop whose zones (#33–#41) come right after.

The numbers are kept here and in each folder's `README.md`, not in the file
names — Python cannot import a module whose name starts with a digit.

The overall direction is inward-out: `domain → adapters → app → ui`, then
`tests`. Each part ends with a **Next** pointer.

---

## Part 0 — Orientation

| # | File | Why now |
|---|---|---|
| 0a | [README.md](README.md) | What firelab is, how to run it, the layout |
| 0b | [ARCHITECTURE.ipynb](ARCHITECTURE.ipynb) | How it is built: components, data flow, rules |
| 0c | [GUIDE.ipynb](GUIDE.ipynb) | How to use it: panels, a first run, troubleshooting |
| 0d | [diagrams/file-connections.mmd](diagrams/file-connections.mmd) | File-level import map — keep it open while reading |

**Next →** Part 1, `domain/`.

## Part 1 — `domain/` · pure logic, no I/O

| # | File | What it gives you |
|---|---|---|
| 1 | [domain/world.py](domain/world.py) | `World`, `Space`, `Coupling` — the nouns everything else uses |
| 2 | [domain/sources.py](domain/sources.py) | Ignition sources, their signatures, and the ground-truth label |
| 3 | [domain/physics.py](domain/physics.py) | Heat, smoke and CO per room, diffusing through doorways (uses #1) |
| 4 | [domain/sensing.py](domain/sensing.py) | Truth → observation: lag, bias, noise, faults (uses #3) |
| 5 | [domain/features.py](domain/features.py) | Readings → feature vectors; never sees the truth |
| 6 | [domain/detector.py](domain/detector.py) | Features → P(fire); the `Detector` protocol (uses #5) |
| 7 | [domain/agent.py](domain/agent.py) | The per-room alarm state machine; proposes commands |
| 8 | [domain/interlocks.py](domain/interlocks.py) | Safety rules the agent cannot override (uses #7) |
| 9 | [domain/tenability.py](domain/tenability.py) | Is a room still survivable; accumulated dose |
| 10 | [domain/roles.py](domain/roles.py) | Kinds of people and how fast they get out |
| 11 | [domain/occupants.py](domain/occupants.py) | Where people are and how they walk a route (uses #1, #10) |
| 12 | [domain/timeline.py](domain/timeline.py) | Evacuation clock: ignition → alarm → building empty |
| 13 | [domain/scoring.py](domain/scoring.py) | Grading detections, misses, false alarms (uses #2, #12) |
| 14 | [domain/history.py](domain/history.py) | Rolling per-room record for charts and CSV |

**Next →** Part 2, `adapters/`.

## Part 2 — `adapters/` · the only code that talks to BuildSim

| # | File | What it gives you |
|---|---|---|
| 15 | [adapters/buildsim/transport.py](adapters/buildsim/transport.py) | One connection pool, one error type |
| 16 | [adapters/buildsim/viewer.py](adapters/buildsim/viewer.py) | Calls scoped to one open 3D viewer tab (uses #15) |
| 17 | [adapters/buildsim/client.py](adapters/buildsim/client.py) | `BuildSim`: one method per URL (uses #15, #16) |
| 18 | [adapters/world_builder.py](adapters/world_builder.py) | BuildSim floor plans → a `World` (uses #1) |
| 19 | [adapters/walkways.py](adapters/walkways.py) | Escape-route search over the walkable graph (uses #18) |
| 20 | [adapters/publisher/layers.py](adapters/publisher/layers.py) | Physics → floor heat maps (truth and belief) |
| 21 | [adapters/publisher/effects.py](adapters/publisher/effects.py) | Physics → fire, smoke, sprinkler particles |
| 22 | [adapters/publisher/beliefs.py](adapters/publisher/beliefs.py) | Agent → room highlights and alerts |
| 23 | [adapters/publisher/hardware.py](adapters/publisher/hardware.py) | Devices → fire doors and the equipment tree (uses #4) |
| 24 | [adapters/publisher/people.py](adapters/publisher/people.py) | Occupants → viewer markers and occupancy (uses #11) |
| 25 | [adapters/publisher/routes.py](adapters/publisher/routes.py) | Escape routes in BuildSim's shape |

`adapters/publisher/__init__.py` re-exports #20–#25 as one module.

**Next →** Part 3, the top of `app/`.

## Part 3 — `app/` · settings, presets, evacuation

| # | File | What it gives you |
|---|---|---|
| 26 | [app/config.py](app/config.py) | `Config`: every runtime setting the UI can edit (uses #10) |
| 27 | [app/presets.py](app/presets.py) | One-click scenario templates |
| 28 | [app/evacuation.py](app/evacuation.py) | Find escape routes and walk people along them (uses #11, #17–#19, #25) |

**Next →** Part 4, `app/engine/`.

## Part 4 — `app/engine/` · the tick loop and all mutable state

| # | File | What it gives you |
|---|---|---|
| 29 | [app/engine/constants.py](app/engine/constants.py) | Loop timings: `REAL_TICK`, `PUBLISH_EVERY` |
| 30 | [app/engine/streaming.py](app/engine/streaming.py) | Snapshot fan-out to open browsers |
| 31 | [app/engine/state.py](app/engine/state.py) | `EngineState`: every mutable value, nothing that acts (uses Part 1–3, #30) |
| 32 | [app/engine/core.py](app/engine/core.py) | **Overview:** the tick loop and the order the zones run in |
| 33 | [app/engine/building.py](app/engine/building.py) | Loading floor plans into the world (uses #17–#19) |
| 34 | [app/engine/session.py](app/engine/session.py) | Fresh run: seed, people, clearing the board |
| 35 | [app/engine/truth.py](app/engine/truth.py) | Zone 1 — WORLD and SENSING, the only readers of truth |
| 36 | [app/engine/intelligence.py](app/engine/intelligence.py) | Zone 2 — readings → features → P(fire) → state machine |
| 37 | [app/engine/recording.py](app/engine/recording.py) | The flight recorder: truth beside reading |
| 38 | [app/engine/actuation.py](app/engine/actuation.py) | Zone 3 — interlocks, then act |
| 39 | [app/engine/publishing.py](app/engine/publishing.py) | Zone 4 — what to write to BuildSim, and when (uses #38) |
| 40 | [app/engine/devices.py](app/engine/devices.py) | Installing, removing and breaking sensors |
| 41 | [app/engine/scenario.py](app/engine/scenario.py) | Igniting sources and applying presets (uses #27, #40) |

**Next →** Part 5, `app/snapshot/`.

## Part 5 — `app/snapshot/` · engine state → the JSON the UI reads

| # | File | What it gives you |
|---|---|---|
| 42 | [app/snapshot/status.py](app/snapshot/status.py) | Header numbers: clock, connection, tallies |
| 43 | [app/snapshot/spaces.py](app/snapshot/spaces.py) | The room table: truth beside reading |
| 44 | [app/snapshot/safety.py](app/snapshot/safety.py) | Tenability and who is still inside |
| 45 | [app/snapshot/population.py](app/snapshot/population.py) | How each role is getting on |
| 46 | [app/snapshot/explain.py](app/snapshot/explain.py) | Why P(fire) is where it is |
| 47 | [app/snapshot/builder.py](app/snapshot/builder.py) | Assembles #42–#45 into the one UI contract |

**Next →** Part 6, `app/api/`.

## Part 6 — `app/api/` + wiring · the HTTP surface

| # | File | What it gives you |
|---|---|---|
| 48 | [app/runtime.py](app/runtime.py) | The single engine instance for the process |
| 49 | [app/api/models.py](app/api/models.py) | Request bodies |
| 50 | [app/api/system.py](app/api/system.py) | Health, state, rooms, config |
| 51 | [app/api/clock.py](app/api/clock.py) | Play, pause, fast-forward, reset |
| 52 | [app/api/scenario.py](app/api/scenario.py) | Fires, nuisances, presets |
| 53 | [app/api/sensors.py](app/api/sensors.py) | Deploy, undeploy, inject faults |
| 54 | [app/api/population.py](app/api/population.py) | Roles and how many of each |
| 55 | [app/api/response.py](app/api/response.py) | Supervision mode and manual commands |
| 56 | [app/api/data.py](app/api/data.py) | History chart and CSV export |
| 57 | [app/api/events.py](app/api/events.py) | The live SSE stream |
| 58 | [app/main.py](app/main.py) | Assembles routers + the built UI — the entry point |

`app/api/__init__.py` collects #50–#57 into `ROUTERS`.

**Next →** Part 7, `ui/`.

## Part 7 — `ui/` · Svelte front end

| # | File | What it gives you |
|---|---|---|
| 59 | [ui/src/main.js](ui/src/main.js) | Mounts the app |
| 60 | [ui/src/lib/store.svelte.js](ui/src/lib/store.svelte.js) | The single store: SSE stream + REST calls |
| 61 | [ui/src/App.svelte](ui/src/App.svelte) | Three-column layout, which panel goes where |
| 62 | [ui/src/lib/Header.svelte](ui/src/lib/Header.svelte) | Clock controls and headline numbers |
| 63 | [ui/src/lib/RoomPicker.svelte](ui/src/lib/RoomPicker.svelte) | Room selector used by #64 |
| 64 | [ui/src/lib/ScenarioPanel.svelte](ui/src/lib/ScenarioPanel.svelte) | Left: ignite sources, presets |
| 65 | [ui/src/lib/Scorecard.svelte](ui/src/lib/Scorecard.svelte) | Left: detections, misses, false alarms |
| 66 | [ui/src/lib/EvacuationPanel.svelte](ui/src/lib/EvacuationPanel.svelte) | Left: evacuation progress |
| 67 | [ui/src/lib/PopulationPanel.svelte](ui/src/lib/PopulationPanel.svelte) | Left: roles and counts |
| 68 | [ui/src/lib/SensorPanel.svelte](ui/src/lib/SensorPanel.svelte) | Left: sensor deployment |
| 69 | [ui/src/lib/DeviceList.svelte](ui/src/lib/DeviceList.svelte) | Per-room device list used by #70 |
| 70 | [ui/src/lib/RoomTable.svelte](ui/src/lib/RoomTable.svelte) | Centre: truth vs reading per room |
| 71 | [ui/src/lib/Chart.svelte](ui/src/lib/Chart.svelte) | Plot used by #72 |
| 72 | [ui/src/lib/RoomDetail.svelte](ui/src/lib/RoomDetail.svelte) | Centre: one room's history |
| 73 | [ui/src/lib/ResponsePanel.svelte](ui/src/lib/ResponsePanel.svelte) | Right: supervision and manual commands |
| 74 | [ui/src/lib/TenabilityPanel.svelte](ui/src/lib/TenabilityPanel.svelte) | Right: survivability |
| 75 | [ui/src/lib/SettingsPanel.svelte](ui/src/lib/SettingsPanel.svelte) | Right: runtime config |
| 76 | [ui/src/lib/Journal.svelte](ui/src/lib/Journal.svelte) | Right: the event journal, blocked commands |

Build plumbing, skim only: `ui/index.html`, `ui/vite.config.js`, `ui/package.json`, `ui/src/app.css`.

**Next →** Part 8, `tests/`.

## Part 8 — `tests/` · the claims, checked

| # | File | Checks |
|---|---|---|
| 77 | [tests/helpers.py](tests/helpers.py) | Shared fixtures and the fake BuildSim |
| 78 | [tests/test_layering.py](tests/test_layering.py) | The import rules between layers |
| 79 | [tests/test_sources.py](tests/test_sources.py) | #2 |
| 80 | [tests/test_physics.py](tests/test_physics.py) | #3 |
| 81 | [tests/test_sensing.py](tests/test_sensing.py) | #4 |
| 82 | [tests/test_detector.py](tests/test_detector.py) | #5–#6 |
| 83 | [tests/test_agent.py](tests/test_agent.py) | #7 |
| 84 | [tests/test_interlocks.py](tests/test_interlocks.py) | #8 |
| 85 | [tests/test_occupants.py](tests/test_occupants.py) | #11 |
| 86 | [tests/test_scoring.py](tests/test_scoring.py) | #12–#13 |
| 87 | [tests/test_history.py](tests/test_history.py) | #14 |
| 88 | [tests/test_walkways.py](tests/test_walkways.py) | #19 |
| 89 | [tests/test_publisher_doors.py](tests/test_publisher_doors.py) | #23 |
| 90 | [tests/test_evacuation.py](tests/test_evacuation.py) | #28 |
| 91 | [tests/test_multifloor.py](tests/test_multifloor.py) | #18, #28 across storeys |
| 92 | [tests/test_publishing_route.py](tests/test_publishing_route.py) | #39 |
| 93 | [tests/test_reset.py](tests/test_reset.py) | #34 |
| 94 | [tests/test_presets.py](tests/test_presets.py) | End to end: #27 through the whole loop |

**End.** Not part of the code path: `Embedded_Intelligence_at_the_edge_Project_Proposal/` (the LaTeX proposal).
