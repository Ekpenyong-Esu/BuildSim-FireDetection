# Experiments

## What it is

The experiments are scripts that run the fire simulation without the browser,
measure what happened, and save the numbers. They drive the same engine the
server runs, tick by tick, from the same seed every time, so a run today gives
the same result as a run tomorrow.

There are three scripts:

| Script | What it does | Output |
|---|---|---|
| `run_experiments.py` | Runs every preset scenario, a noise sweep, a sensor-fault sweep, and a scaling test | `results/results.json` |
| `containment.py` | Runs the office fire three times: no response, full response, sprinkler only, and counts the rooms that became unsafe | `results/containment.json` |
| `plot_results.py` | Draws the report's two evaluation charts from `results.json` with matplotlib | `../Embedded_Intelligence_at_the_edge_Project_Proposal/images/chart_*.png` |

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
   images folder. To change how a chart looks, edit the two functions in that
   file; it is plain matplotlib.

4. Rebuild the report, which includes those PNGs:

   ```
   cd Embedded_Intelligence_at_the_edge_Project_Proposal && make
   ```

   Steps 2 and 3 are also available there as `make data`, and step 3 alone as
   `make charts`.

## Comparing the two detectors

The runs above use the hand-written fusion rule. To score the same scenarios
with the language-model detector instead, point it at your endpoint and set the
detector before running:

```
export LLM_BASE_URL=https://your-endpoint/v1 LLM_API_KEY=... LLM_MODEL=...
FIRELAB_DETECTOR=llm .venv/bin/python experiments/run_experiments.py
```

The model answers in the background and the rule scores any room it has no
fresh verdict for, so the numbers measure the pair, not the model alone. They
are also not repeatable from the seed the way the rule's are.

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
a change to the engine, read Section 11 against the new charts and update them.
