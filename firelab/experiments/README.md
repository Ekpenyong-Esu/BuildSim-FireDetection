# Experiments

## What it is

The experiments are scripts that run the fire simulation without the browser,
measure what happened, and save the numbers. They drive the same engine the
server runs, tick by tick, from the same seed every time, so a run today gives
the same result as a run tomorrow.

There are four scripts:

| Script | What it does | Output |
|---|---|---|
| `run_experiments.py` | Runs every preset scenario, a noise sweep, a sensor-fault sweep, and a scaling test with the fusion rule | `results/results.json` |
| `containment.py` | Runs the office fire three times: no response, full response, sprinkler only, and counts the rooms that became unsafe | `results/containment.json` |
| `compare_detectors.py` | Runs nine of the same scenarios with the language-model detector, paced to the wall clock the way the live engine is | `results/results_llm.json` |
| `plot_results.py` | Draws the report's evaluation charts from the results with matplotlib | `../Embedded_Intelligence_at_the_edge_Project_Proposal/images/chart_*.png` |

Every scenario is run in the same office, A3505 on the top floor, with the room
and its neighbours instrumented, 130 people scattered by the default seed, and
the default thresholds. Each run lasts 20 simulated minutes.

## Why it is needed

The final report has to show that the system works with measured evidence, not
with a description of how it should work. Numbers such as "the office fire was
confirmed 106 s after ignition", "no nuisance raised a false alarm at any noise
level", and "the tick budget breaks at about 450 monitored rooms" all come from
these scripts. Reading them off the dashboard by hand would be slow, would not
be repeatable, and would miss the cases nobody thought to try.

The experiments also work as a safety net. If you change a detector weight, a
threshold, a dwell time, or the physics, one run tells you whether real fires
are still caught, whether cooking has started to alarm, and whether a tick still
fits in its 250 ms budget. Two things in the report were only found this way:
the dead smoke detector leaves the fire room three thousandths below the confirm
threshold, and closing the fire doors makes the fire room hotter while
protecting its neighbours.

## How to use it

1. Start BuildSim, which the experiments need for the floor plans:

   ```
   cd buildingsim && make run
   ```

   Nothing is drawn in the viewer during a run; publishing is switched off.

2. From the `firelab` folder, run the measurements. This takes several minutes
   because the scaling test alone times ticks over the whole building.

   ```
   .venv/bin/python experiments/run_experiments.py
   .venv/bin/python experiments/containment.py
   ```

   Each script prints a one-line summary per scenario as it goes and writes its
   JSON file into `experiments/results/`.

3. Draw the charts:

   ```
   .venv/bin/python experiments/plot_results.py
   ```

   This writes `chart_office_fire.png` and `chart_scaling.png` into the report's
   images folder, and `chart_detectors.png` as well if `results_llm.json`
   exists. To change how a chart looks, edit the functions in that file; it is
   plain matplotlib.

4. Rebuild the report, which includes those PNGs:

   ```
   cd Embedded_Intelligence_at_the_edge_Project_Proposal && make
   ```

   Steps 2 and 3 are also available there as `make data`, step 3 alone as
   `make charts`, and the model comparison as `make compare`.

## Comparing the two detectors

The runs above use the hand-written fusion rule. `compare_detectors.py` scores
nine of the same scenarios with the language-model detector: the six presets,
kitchen cooking at 2x and 3x noise, and the office fire with a stuck smoke
detector. Point it at your endpoint (or fill in `firelab/.env`) and run it:

```
export LLM_BASE_URL=https://your-endpoint/v1 LLM_API_KEY=... LLM_MODEL=...
.venv/bin/python experiments/compare_detectors.py
```

It is slow on purpose. The rule's harness runs twenty simulated minutes in a
few seconds because nothing waits; the model takes about eight real seconds an
answer and a verdict is only good for a minute of simulated time, so the script
sleeps between ticks exactly as the live engine paces itself, at the speed the
detector has measured it can keep up with (about 3x for the endpoint used in the
report). One scenario is therefore six to seven real minutes and the whole set
about an hour. The script is resumable: each finished scenario is written to
`results/results_llm.json` at once and skipped on the next start.

Each run carries the same fields as the rule's plus an `llm` block: the model
name, how many questions were asked, answered and failed, the median and worst
answer time, the speed the clock was capped at, the share of the fire room's
samples the model scored (`model_share`; the rule covers the rest), the highest
probability the model itself gave, a 5-second trace of who scored the room, and
every journal line in which the model gave its reason.

The numbers measure the pair, not the model alone, and they are not repeatable
from the seed the way the rule's are: the model is asked at temperature 0, but
what it is asked depends on real answer times. Run it twice to see how much
moves.

`FIRELAB_DETECTOR=llm .venv/bin/python experiments/run_experiments.py` still
works but is not what you want: unpaced, the run is over before the first
answer arrives and the rule scores everything.

## Reading the results

`results.json` has five sections:

- `presets`: one entry per scenario with the time the room started
  investigating, the time it confirmed, the scoreboard's detections, misses
  and false alarms, the evacuation time (RSET), the peak true temperature and
  smoke, the highest P(fire) reached, whether the sprinkler ran, any commands
  the interlocks blocked, the first journal lines, and the full 5-second time
  series of truth, readings and P(fire).
- `open_loop`: the office fire with the agent's commands dropped.
- `noise`: fire and cooking at sensor noise 0, 1, 2 and 3 times normal.
- `faults`: the office fire with the smoke detector stuck, dropping out,
  drifting, or dead.
- `scaling`: median and worst wall time of one tick for 10 to 956 monitored
  rooms, at real time and at 40 times real time.

## Changing an experiment

The settings are constants at the top of `run_experiments.py`: the room, the
step size, and the length of a run. To try a different room, change `ROOM` to
another `level/name` key. To add a scenario, add a preset in
`firelab/app/presets.py` and it will be picked up by the preset loop. To change a
chart, edit `plot_results.py`; the `series` helper there is the only place that
knows the column order of a time-series row.

The numbers quoted in the prose of the report are typed into the text, so after
a change to the engine, read the report's "Evaluation and experiments" section
against the new charts and update them.
