"""Draw the report's evaluation charts from the experiment results.

    cd firelab && .venv/bin/python experiments/plot_results.py

Reads experiments/results/results.json (written by run_experiments.py) and writes
two PNGs into the report's images folder:

    chart_office_fire.png   the office fire as the system saw it
    chart_scaling.png       wall time of one tick against monitored rooms
    chart_detectors.png     P(fire) from the rule and from the model, four scenarios
                            (only when results_llm.json exists, from compare_detectors.py)

Plain matplotlib, nothing else. Edit the functions below to change a chart.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to files; no window needed
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results" / "results.json"
RESULTS_LLM = HERE / "results" / "results_llm.json"
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


def detectors(results: dict, results_llm: dict) -> None:
    """Four panels of P(fire): the rule's run in blue, the model's in orange.

    In the model's run the rule scores the room whenever the model has no fresh
    verdict, and those stretches are drawn grey so the reader can see who was
    speaking. The trace comes from the harness, sampled every 5 s.
    """
    panels = (("office-fire", "Office fire"), ("overnight-smoulder", "Overnight smoulder"),
              ("kitchen-cooking", "Kitchen cooking"), ("blind-spot", "Fire, dead smoke detector"))
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.6), sharex=True, sharey=True)
    for ax, (preset, title) in zip(axes.flat, panels):
        rule = series(results, preset)
        ax.plot(rule["t"], rule["p_fire"], color=READING, lw=1.4, label="fusion rule")
        run = next((p for p in results_llm["presets"] if p["preset"] == preset), None)
        if run is not None:
            trace = run["llm"]["trace"]
            # Consecutive samples with the same scorer make one segment.
            start = 0
            while start < len(trace):
                end = start
                while end + 1 < len(trace) and trace[end + 1][2] == trace[start][2]:
                    end += 1
                segment = trace[start:end + 2]  # overlap one point so the line is unbroken
                model = trace[start][2] == "model"
                ax.plot([r[0] for r in segment], [r[1] for r in segment],
                        color=TRUTH if model else GREY, lw=1.4 if model else 1.0,
                        ls="-" if model else ":",
                        label=("language model" if model else "rule covering for the model") if start == 0 or not any(
                            l.get_label() == ("language model" if model else "rule covering for the model") for l in ax.lines) else None)
                start = end + 1
        for name, level, colour in THRESHOLDS:
            ax.axhline(level, color=colour, ls="--", lw=0.7)
        ax.set_title(title, fontsize=9)
        ax.set_ylim(0, 1.05)
        ax.set_xlim(0, 1200)
    for ax in axes[1]:
        ax.set_xlabel("seconds since ignition")
    for ax in axes[:, 0]:
        ax.set_ylabel("P(fire)")
    handles, labels = axes[0][0].get_legend_handles_labels()
    for ax in axes.flat[1:]:
        for h, l in zip(*ax.get_legend_handles_labels()):
            if l not in labels:
                handles.append(h); labels.append(l)
    fig.legend(handles, labels, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(IMAGES / "chart_detectors.png", dpi=200)
    plt.close(fig)


def main() -> None:
    results = load()
    IMAGES.mkdir(exist_ok=True)
    office_fire(results)
    scaling(results)
    print("wrote", IMAGES / "chart_office_fire.png", "and", IMAGES / "chart_scaling.png")
    if RESULTS_LLM.exists():
        detectors(results, json.loads(RESULTS_LLM.read_text()))
        print("wrote", IMAGES / "chart_detectors.png")


if __name__ == "__main__":
    main()
