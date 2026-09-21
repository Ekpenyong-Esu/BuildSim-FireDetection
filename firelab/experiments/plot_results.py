"""Draw the report's evaluation charts from the experiment results.

    cd firelab && .venv/bin/python experiments/plot_results.py

Reads experiments/results/results.json (written by run_experiments.py) and writes
two PNGs into the report's images folder:

    chart_office_fire.png   the office fire as the system saw it (Figure 8)
    chart_scaling.png       wall time of one tick against monitored rooms (Figure 9)

Plain matplotlib, nothing else. Edit the functions below to change a chart.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to files; no window needed
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results" / "results.json"
IMAGES = HERE.parent / "Embedded_Intelligence_at_the_edge_Project_Proposal" / "images"

# The report's palette.
TRUTH = "#e25822"  # orange: what is really in the room
READING = "#1c68c4"  # blue: what the sensor reported
GREY = "#777777"
THRESHOLDS = (("investigate", 0.35, "#22a04a"), ("pre-alarm", 0.55, "#f59e0b"), ("confirm", 0.75, "#e11d48"))
TICK_BUDGET_MS = 250  # the engine wakes every 250 ms of real time
TEMPERATURE_RANGE_C = 250  # the heat detector's clamp (domain/sensing.py)

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.grid": True,
    "grid.color": "#dddddd",
    "grid.linewidth": 0.5,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
})


def load() -> dict:
    return json.loads(RESULTS.read_text())


def series(results: dict, preset: str) -> dict[str, list]:
    """One preset's time series as named columns; gaps stay as None."""
    rows = next(p for p in results["presets"] if p["preset"] == preset)["series"]
    names = ("t", "truth_temp", "truth_smoke", "truth_co", "read_temp", "read_smoke", "read_co", "p_fire")
    return {name: [row[i] for row in rows] for i, name in enumerate(names)}


def office_fire(results: dict, seconds: int = 600) -> None:
    """Three stacked panels: temperature, smoke, and P(fire) with the thresholds."""
    s = series(results, "office-fire")
    run = next(p for p in results["presets"] if p["preset"] == "office-fire")
    t = s["t"]
    fig, (ax_t, ax_s, ax_p) = plt.subplots(3, 1, figsize=(7.2, 6.4), sharex=True)

    ax_t.plot(t, s["truth_temp"], color=TRUTH, lw=1.4, label="truth")
    ax_t.plot(t, s["read_temp"], color=READING, lw=1.4, label="reading")
    ax_t.axhline(TEMPERATURE_RANGE_C, color=GREY, ls="--", lw=0.9, label="detector range")
    ax_t.set_ylabel("temperature (°C)")
    ax_t.legend(loc="lower right")

    ax_s.plot(t, s["truth_smoke"], color=TRUTH, lw=1.4, label="truth")
    ax_s.plot(t, s["read_smoke"], color=READING, lw=1.4, label="reading")
    ax_s.set_ylabel("smoke (1/m)")
    ax_s.legend(loc="lower right")

    ax_p.plot(t, s["p_fire"], color=READING, lw=1.4, label="P(fire)")
    for name, level, colour in THRESHOLDS:
        ax_p.axhline(level, color=colour, ls="--", lw=0.9, label=f"{name} {level:.2f}")
    # The measured state changes, so the dwells can be read off the trace. The
    # pre-alarm time is read from the journal lines the run kept.
    pre_alarm = next((float(line.split("s ")[0]) for line in run["journal"] if "-> PRE_ALARM" in line), None)
    for at in (run["investigating_at"], pre_alarm, run["confirmed_at"]):
        if at is not None:
            ax_p.axvline(at, color=GREY, lw=0.8)
    ax_p.set_ylim(0, 1.05)
    ax_p.set_ylabel("P(fire)")
    ax_p.set_xlabel("seconds since ignition")
    ax_p.legend(loc="lower right", ncol=2)

    ax_p.set_xlim(0, seconds)
    fig.tight_layout()
    fig.savefig(IMAGES / "chart_office_fire.png", dpi=200)
    plt.close(fig)


def scaling(results: dict) -> None:
    """Median tick time against monitored rooms, at 1x and 40x, with the budget line."""
    rows = results["scaling"]
    at = lambda factor: sorted((r["rooms"], r["median_ms"]) for r in rows if r["factor"] == factor)
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    for factor, colour, marker in ((1.0, READING, "o"), (40.0, TRUTH, "s")):
        points = at(factor)
        ax.plot([p[0] for p in points], [p[1] for p in points], color=colour, marker=marker, ms=4, lw=1.4,
                label=f"{factor:g}× real time")
    ax.axhline(TICK_BUDGET_MS, color="#e11d48", ls="--", lw=1.0, label=f"{TICK_BUDGET_MS} ms tick budget")
    ax.set_xlim(0, 1000)
    ax.set_ylim(0, 420)
    ax.set_xlabel("monitored rooms (all three modalities)")
    ax.set_ylabel("one tick, median wall time (ms)")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(IMAGES / "chart_scaling.png", dpi=200)
    plt.close(fig)


def main() -> None:
    results = load()
    IMAGES.mkdir(exist_ok=True)
    office_fire(results)
    scaling(results)
    print("wrote", IMAGES / "chart_office_fire.png", "and", IMAGES / "chart_scaling.png")


if __name__ == "__main__":
    main()
