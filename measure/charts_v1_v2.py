"""v1 against v2: the same three sizes, before and after the fixes of our first round of checks (extract cache, 565a0a9).

    python measure/charts_v1_v2.py      # writes measure/results_v2/v1_vs_v2.png

Reads measure/results/summary.csv (v1: every start parses the 14 zips) and
measure/results_v2/summary.csv (v2: mode generated = a later start, which reads data/clean;
mode first_start = data/clean deleted first, 100% only). Modelled on the template's chart.
Bars are the mean of the runs; the error bars are min and max.
Titles say what is shown, not what to conclude: the README says that.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                     # no window: write PNG files only
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SIZES = ["25%", "50%", "100%"]
PANELS = [  # (step in v1, step in v2), unit, title
    (("full_run", "full_run"), "s", "Full run, docker compose up to dashboard ready (s)"),
    (("parse", "read_extract"), "s", "Getting the rows (s)\nv1 and first start: parse of the 14 zips; v2: read_extract"),
    (("peak_mem_loader_full_run",) * 2, "MiB", "Peak memory of the loader container (MiB)"),
    (("query_drugs_for_condition_with_index_migraine",) * 2, "ms",
     "Main query with GIN index, migraine (ms)\nruns x 3 repetitions"),
]
SERIES = [("v1 (every start parses)", "#9aa5b1"), ("v2 later start (extract)", "#2b6cb0"),
          ("v2 first start (parse + write extract)", "#dd6b20")]


def series(s, step, unit, mode, sizes):
    """Mean, min and max of one step at the given sizes, in that order."""
    d = s[(s["step"] == step) & (s["unit"] == unit) & (s["mode"] == mode)].set_index("size").loc[sizes]
    return d["mean"], d["min"], d["max"]


def bar(ax, x, mean, lo, hi, width, label, color):
    err = [(mean - lo).clip(lower=0), (hi - mean).clip(lower=0)]
    b = ax.bar(x, mean, width, yerr=err, capsize=3, label=label, color=color)
    ax.bar_label(b, fmt=lambda v: f"{v:.3g}" if v < 1000 else f"{v:.0f}", fontsize=8, padding=2)


def main():
    v1 = pd.read_csv(ROOT / "measure/results/summary.csv")
    v2 = pd.read_csv(ROOT / "measure/results_v2/summary.csv")
    fig, axes = plt.subplots(1, 4, figsize=(18, 4.8))
    width = 0.27
    for ax, ((step1, step2), unit, title) in zip(axes, PANELS):
        for i, (s, step, mode) in enumerate([(v1, step1, "generated"), (v2, step2, "generated")]):
            x = [g + (i - 1) * width for g in range(len(SIZES))]
            bar(ax, x, *series(s, step, unit, mode, SIZES), width, *SERIES[i])
        # The first starts ran at 100% only; they parse, so the middle panel shows their parse.
        first_step = "parse" if step2 == "read_extract" else step2
        if not v2[(v2["step"] == first_step) & (v2["mode"] == "first_start")].empty:
            bar(ax, [len(SIZES) - 1 + width], *series(v2, first_step, unit, "first_start", ["100%"]), width, *SERIES[2])
        ax.set_xticks(range(len(SIZES)), SIZES)
        ax.set_xlabel("data size (share of the usable labels)", fontsize=8)
        ax.set_title(title, fontsize=10)
        ax.set_ylabel(unit)
        ax.spines[["top", "right"]].set_visible(False)
    # One legend for all panels, below the figure, so it covers no bar.
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=3, fontsize=9, frameon=False)
    fig.suptitle("v1 vs v2, mean of 3 runs (first start: 3 runs at 100%); error bars min-max; "
                 "4 vCPU VM, everything in Docker", fontsize=10)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    out = ROOT / "measure/results_v2/v1_vs_v2.png"
    fig.savefig(out, dpi=130)
    print(out)


if __name__ == "__main__":
    main()
