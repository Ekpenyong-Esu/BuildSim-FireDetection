# domain — Pure Logic (no I/O)

Part 1 of [READING_ORDER.md](../READING_ORDER.md). Previous: Part 0, orientation.

How to read (numbers are global across firelab):

- **#1** `world.py` — `World`/`Space`/`Coupling` — the nouns everything uses
- **#2** `sources.py` — ignition sources and the ground-truth label
- **#3** `physics.py` — heat, smoke, CO per room (imports `world`)
- **#4** `sensing.py` — truth → observation (imports `physics`)
- **#5** `features.py` — readings → features
- **#6** `detector.py` — features → P(fire) (imports `features`)
- **#7** `agent.py` — alarm state machine
- **#8** `interlocks.py` — rules the agent cannot override (imports `agent`)
- **#9** `tenability.py` — is a room survivable
- **#10** `roles.py` — kinds of people
- **#11** `occupants.py` — where people are (imports `world`+`roles`)
- **#12** `timeline.py` — ignition → alarm → building empty
- **#13** `scoring.py` — grading the system (imports `sources`+`timeline`)
- **#14** `history.py` — rolling record for charts/CSV

Next → #15 [`adapters/buildsim/transport.py`](../adapters/README.md).

See `diagram.mmd`.
