"""v2 against v3: the same protocol on the code before and after the second round of fixes.

    python measure/charts_v2_v3.py      # writes measure/results_v3/v2_vs_v3.png

Reads measure/results_v2/summary.csv and measure/results_v3/summary.csv (mode generated = a
later start, which reads data/clean; mode first_start = data/clean deleted first, 100% only).
The pipeline code is the same in both; v3 skips the zip checks on a later start.
Bars are the mean of the runs; the error bars are min and max. Modelled on charts_v1_v2.py.
Titles say what is shown, not what to conclude: verdicts.md says that.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                     # no window: write PNG files only
import matplotlib.pyplot as plt
import pandas as pd

from charts_v1_v2 import SIZES, bar, series   # same helpers as the v1-v2 chart

ROOT = Path(__file__).resolve().parent.parent
PANELS = [  # step (later start), step (first start), unit, title
    ("full_run", "full_run", "s", "Full run, docker compose up to dashboard ready (s)"),
    ("read_extract", "parse", "s", "Getting the rows (s)\nlater start: read_extract; first start: parse of the 14 zips"),
    ("peak_mem_loader_full_run", "peak_mem_loader_full_run", "MiB", "Peak memory of the loader container (MiB)"),
    ("query_drugs_for_condition_with_index_migraine", None, "ms",
     "Main query with GIN index, migraine (ms)\nruns x 3 repetitions"),
]
SERIES = [("v2 later start", "#90cdf4"), ("v3 later start", "#2b6cb0"),
          ("v2 first start", "#fbd38d"), ("v3 first start", "#dd6b20")]


def main():
    v2 = pd.read_csv(ROOT / "measure/results_v2/summary.csv")
    v3 = pd.read_csv(ROOT / "measure/results_v3/summary.csv")
    fig, axes = plt.subplots(1, 4, figsize=(18, 4.8))
    width = 0.2
    for ax, (step, first_step, unit, title) in zip(axes, PANELS):
        for i, s in enumerate([v2, v3]):           # later starts: every size
            x = [g + (i - 1.5) * width for g in range(len(SIZES))]
            bar(ax, x, *series(s, step, unit, "generated", SIZES), width, *SERIES[i])
        if first_step:                             # first starts: 100% only, no query benchmark
            for i, s in enumerate([v2, v3]):
                bar(ax, [len(SIZES) - 1 + (i + 0.5) * width], *series(s, first_step, unit, "first_start", ["100%"]),
                    width, *SERIES[2 + i])
        ax.set_xticks(range(len(SIZES)), SIZES)
        ax.set_xlabel("data size (share of the usable labels)", fontsize=8)
        ax.set_title(title, fontsize=10)
        ax.set_ylabel(unit)
        ax.spines[["top", "right"]].set_visible(False)
    # One legend for all panels, below the figure, so it covers no bar.
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=4, fontsize=9, frameon=False)
    fig.suptitle("v2 vs v3, mean of 3 runs (first start: 3 runs at 100%); error bars min-max; "
                 "4 vCPU VM, everything in Docker", fontsize=10)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    out = ROOT / "measure/results_v3/v2_vs_v3.png"
    fig.savefig(out, dpi=130)
    print(out)


if __name__ == "__main__":
    main()
