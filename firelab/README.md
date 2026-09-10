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

## Quick start

```bash
# terminal 1 — the building
cd ../buildingsim && make build && ./bin/buildsim start --port 9090

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
  sources.py     what a fire emits over time (and its ground-truth label)
  physics.py     how heat, smoke and CO spread between rooms
  sensing.py     truth -> observation: lag, bias, noise, quantisation, faults
  features.py    readings -> features (never sees the truth)
  detector.py    features -> P(fire); a Protocol, so a model can replace it
  agent.py       per-room state machine; proposes commands
  interlocks.py  which commands are allowed to happen
  occupants.py   where people are and how they walk a route
  scoring.py     grades the run against the label each source carries
  history.py     a short rolling record per space, for charts and CSV

adapters/   everything that speaks HTTP to BuildSim
  buildsim.py       the HTTP client, one method per endpoint
  world_builder.py  BuildSim floor plans -> a physics World
  publisher.py      simulation state -> BuildSim payload shapes

app/        the impure edge
  config.py      runtime settings
  engine.py      the tick loop; the only mutable state
  evacuation.py  route lookup + walking people along it
  snapshot.py    engine state -> the JSON the UI reads
  presets.py     one-click scenarios: a template plus a room
  main.py        REST + SSE

ui/         Svelte + Vite front end, one component per panel
tests/      domain tests; they run without anything else being up
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
