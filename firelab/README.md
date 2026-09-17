# firelab

Fire detection and autonomous response for [BuildSim](../buildingsim). One
control-plane service with a browser UI: you place ignition sources, deploy
sensors, break them on purpose, and watch whether the system can still tell a
real fire from burnt toast — and what it does about it.

firelab does not replace the BuildSim viewer. It drives it. Keep both tabs
open: firelab on <http://127.0.0.1:8090> to control the simulation, BuildSim on
<http://127.0.0.1:9090> to see the building react.

> firelab writes `/api/entities` and `/api/occupancy`. Do not run `occupancysim`
> at the same time — both replace the whole collection on every write.

> New to the code? Follow [READING_ORDER.md](READING_ORDER.md) — every file
> numbered in the order to read it, folder by folder.

## Quick start

```bash
# terminal 1 — the building
cd ../buildingsim && make run

# terminal 2 — firelab
cd firelab && make build && make run
```

Then open <http://127.0.0.1:8090>:

1. **Sensor deployment** — filter rooms, tick a handful, press *Deploy*. The
   devices appear in BuildSim's equipment tree too.
2. **Scenario** — pick a room, pick a source, press *Ignite*.
3. Press **Run** in the header and raise the speed to 30–60×.
4. Watch the **Rooms** table: truth on the left, sensor readings in the middle,
   P(fire) and the alarm state on the right.

`make dev` runs the API with reload; run `cd ui && npm run dev` beside it for
hot-reloading UI work on <http://127.0.0.1:5173>.

## What it models

**Sources** (`domain/sources.py`) — the source kind is also the ground-truth
label, which is what makes supervised training possible later.

| Kind | Heat | Smoke | CO | The point |
|---|---|---|---|---|
| `flaming` | t² growth to a cap | yes | yes | the easy case |
| `smouldering` | almost none | dense | very high | only CO catches it |
| `cooking` | small, transient | yes | trace | the classic false alarm |
| `dust` | none | yes | none | smoke without fire |
| `steam` | none | yes | none | smoke without fire |

**Physics** (`domain/physics.py`) — one lumped node per room. Heat, smoke and
CO relax towards a source-driven equilibrium and diffuse to neighbours across
door-gated couplings taken from BuildSim's walkable graph. An active sprinkler
cuts heat release and washes smoke out, so *the control loop is closed*: what
the agent does changes what the sensors will see.

**Sensing** (`domain/sensing.py`) — the truth→observation boundary. Every
device applies lag, calibration bias, Gaussian noise, quantisation and clamping,
and can be given a fault: `stuck`, `dropout`, `drift`, or `dead`. Inject faults
from the Rooms table by expanding a row.

**Intelligence** (`domain/features.py`, `detector.py`, `agent.py`) — features
are computed from readings only; nothing downstream of the sensors is allowed to
see the truth. The shipped detector is a hand-written multi-modal fusion rule
(level, rate of rise, temperature rise, CO/smoke ratio, neighbour agreement).
It implements the `Detector` protocol, so a trained model can replace it without
the agent noticing. The agent is a per-room state machine with dwell times:

```
NORMAL → INVESTIGATING → PRE_ALARM → CONFIRMED → CLEARING
```

**Actuation** (`domain/interlocks.py`) — the agent proposes, the interlocks
dispose. Three rules the agent cannot override:

- sprinklers need heat corroboration — smoke alone never releases water;
- fire doors fail unlocked, always;
- a room that is occupied or on an active escape route cannot be sealed.

Every blocked command is written to the journal, which is where the interesting
lessons show up. A smouldering fire, for example, confirms on CO alone and then
gets its sprinkler request *refused* for lack of heat.

## Layout

```
domain/     pure: standard library only, no clock, no network, no BuildSim
  world.py       the nouns: Space, Coupling, World — what a building *is*
  sources.py     what a fire emits over time (and its ground-truth label)
  physics.py     how heat, smoke and CO spread between rooms
  sensing.py     truth -> observation: lag, bias, noise, quantisation, faults
  features.py    readings -> features (never sees the truth)
  detector.py    features -> P(fire); a Protocol, so a model can replace it
  agent.py       per-room state machine; proposes commands
  interlocks.py  which commands are allowed to happen
  roles.py       who is in the building, and how fast they get out
  occupants.py   where people are and how they walk a route
  scoring.py     was the alarm right? detections, misses, false alarms
  timeline.py    was it in time? ignition -> alarm -> building empty (RSET)
  history.py     a short rolling record per space, for charts and CSV

adapters/   everything that speaks HTTP to BuildSim
  buildsim.py       the HTTP client, one method per endpoint
  world_builder.py  BuildSim floor plans -> a physics World
  exits.py          guessing each upper level's stairwell exits
  publisher/        simulation state -> BuildSim payload shapes
    layers.py         physics -> floor heat maps
    effects.py        physics -> fire, smoke and sprinkler particles
    beliefs.py        agent   -> room highlights and alerts
    people.py         people  -> viewer markers and occupancy
    hardware.py       devices -> fire doors and the equipment tree

app/        the impure edge
  config.py      runtime settings
  runtime.py     the one engine instance for the process
  evacuation.py  route lookup + walking people along it
  presets.py     one-click scenarios: a template plus a room
  main.py        assembles the app: routers + static files
  engine/        the tick loop; the only mutable state
    state.py       every mutable attribute, and nothing that acts on it
    core.py        the lifecycle and *when* each zone runs
    building.py    floor plans -> the world the physics runs on
    session.py     reseeding, re-scattering people, clearing the board
    truth.py       WORLD and SENSING: the only readers of the ground truth
    intelligence.py  readings -> features -> P(fire) -> the room state machine
    recording.py   the flight recorder: truth beside reading
    actuation.py   the single door between deciding and doing
    scenario.py    igniting sources and applying presets
    devices.py     installing, removing and breaking sensors
    publishing.py  deciding what to write to BuildSim, and when
    streaming.py   fan-out of snapshots to open browsers
  snapshot/      engine state -> the JSON the UI reads
    builder.py     assembles the one dictionary the UI reads
    status.py      clock, connection, headline counts
    spaces.py      the room table: truth beside reading
    safety.py      tenability and evacuation progress
    population.py  how each role is getting on
    explain.py     why P(fire) is where it is
  api/           REST + SSE, one router per thing you can ask for
    models.py      the request bodies
    system.py      health, state, rooms, config
    events.py      the SSE stream
    clock.py       play, pause, fast-forward, reset
    scenario.py    fires, nuisances, presets
    population.py  roles and how many of each
    sensors.py     deploy, undeploy, inject faults
    response.py    supervision mode and manual commands
    data.py        history and CSV export

ui/         Svelte + Vite front end, one component per panel
tests/      domain tests, one file per module; they run with nothing else up
```

The dependency arrow only ever points inward: `app → adapters → domain`.
Nothing in `domain/` imports anything outside it, which is why it can be tested
with no services running.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/state` | full snapshot |
| `GET` | `/api/events` | server-sent events, one snapshot per tick |
| `GET` | `/api/rooms` | every space, for the pickers |
| `GET`/`PUT` | `/api/config` | runtime configuration |
| `POST` | `/api/clock` | `{seconds, factor, running}` |
| `POST` | `/api/scenario/ignite` | `{space, kind, growth, delay, peak_kw}` |
| `DELETE` | `/api/scenario/{id}` | remove a source |
| `GET` | `/api/presets` | the one-click scenario catalogue |
| `POST` | `/api/scenario/preset` | `{preset, space}` |
| `GET` | `/api/history?space=` | recent samples for one room |
| `GET` | `/api/export.csv` | the whole run, labelled, as CSV |
| `POST` | `/api/sensors/deploy` | `{spaces, modalities}` |
| `POST` | `/api/sensors/undeploy` | `{spaces}` |
| `POST` | `/api/sensors/fault` | `{device_id, fault}` |
| `POST` | `/api/agent/mode` | `{auto}` |
| `POST` | `/api/actuators/command` | manual command, still interlocked |
| `POST` | `/api/reset` · `/api/reload` | reset state · reload floors |

## What firelab publishes to BuildSim

Truth and belief are published to *different* endpoints on purpose, so a false
positive is visible on screen as a mismatch between them.

| Endpoint | Carries |
|---|---|
| `PUT /api/room-layers` | true temperature, smoke, CO — and, separately, P(fire) |
| `PUT /api/effects` | fire, smoke and sprinkler primitives |
| `PUT /api/alerts` | the agent's current alarms |
| `PUT /api/doors` | fire-door state |
| `PUT /api/entities`, `/api/occupancy` | occupants and where they are |
| `PUT /api/sensors/{id}/value` | each device's latest reading |
| session `highlights` | red / orange / yellow rooms by alarm state |

## Tests

```bash
make test
```

## Not built yet

- a trained detector (autoencoder or isolation forest) fed from recorded runs;
- fire-spread prediction ahead of the sensors;
- splitting the zones into separate containers over MQTT.

The seams for all three already exist: `Detector` is a protocol, the domain is
import-clean, and the adapters are the only code that knows a network exists.
