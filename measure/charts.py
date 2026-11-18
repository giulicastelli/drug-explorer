"""Charts of the measurements, from summary.csv (written by benchmark.py).

    python measure/charts.py                       # reads and writes measure/results
    python measure/charts.py --results some/folder

Each chart shows the mean of the runs; the error bars are min and max.
Titles say what is shown, not what to conclude: the README says that.
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                     # no window: write PNG files only
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CONDITIONS = ["migraine", "hypertension", "epilepsy", "asthma", "cancer"]   # as in loader/bench_queries.py
MODES = [("with_index", "with GIN index"), ("without_index", "without index (scan of stored tsv)"),
         ("on_the_fly", "on the fly (to_tsvector per row)")]


def pick(s, step, unit, mode="generated"):
    """The rows of one step, one per size, sorted by size."""
    d = s[(s["step"] == step) & (s["unit"] == unit) & (s["mode"] == mode)].copy()
    d["pct"] = d["size"].str.rstrip("%").astype(float)
    return d.sort_values("pct").set_index("size")


def bars(ax, groups, labels, values, errors=None, legend=True):
    """Grouped bars: one group per x position, one bar per series, each bar labelled with its value."""
    width = 0.8 / len(labels)
    for i, label in enumerate(labels):
        x = [g + (i - (len(labels) - 1) / 2) * width for g in range(len(groups))]
        yerr = errors[i] if errors else None
        b = ax.bar(x, values[i], width, label=label, yerr=yerr, capsize=3)
        ax.bar_label(b, fmt=lambda v: f"{v:.3g}" if v < 1000 else f"{v:.0f}", fontsize=7, padding=2)
    ax.set_xticks(range(len(groups)), groups)
    if legend:
        ax.legend(fontsize=7)


def minmax(d):
    """Error bar lengths below and above the mean."""
    return [(d["mean"] - d["min"]).clip(lower=0).tolist(), (d["max"] - d["mean"]).clip(lower=0).tolist()]


def time_vs_size(s, out):
    rows = pick(s, "rows_loaded", "rows")["mean"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    # Left: the big steps (seconds to a minute); right: the small ones, on their own scale.
    panels = [(axes[0], [("parse", "parse: read all 14 zips"), ("read_extract", "read_extract: read data/clean (v2)"),
                         ("pipeline_total", "pipeline (after download)"),
                         ("full_run", "full run (up to dashboard ready)")]),
              (axes[1], [("copy", "COPY (with tsv computed)"), ("index_build", "GIN index build"),
                         ("analyze", "ANALYZE")])]
    for ax, series in panels:
        for step, label in series:
            d = pick(s, step, "s")
            if d.empty:
                continue
            x = rows.loc[d.index] / 1e3
            line = ax.errorbar(x, d["mean"], yerr=minmax(d), marker="o", capsize=3, label=label)
            # Perfectly linear growth from the smallest size: value x (rows / rows at the smallest size).
            ax.plot(x, d["mean"].iloc[0] * x / x.iloc[0], "--", color=line[0].get_color(), alpha=0.5,
                    label=f"{label}: linear from {d.index[0]}")
            for xi, yi, size in zip(x, d["mean"], d.index):
                ax.annotate(size, (xi, yi), textcoords="offset points", xytext=(4, -12), fontsize=7)
        ax.set_xlabel("labels loaded (thousands)")
        ax.set_ylabel("time (s), mean of runs")
        ax.set_ylim(bottom=0)
        ax.set_xlim(left=0)
        ax.legend(fontsize=7)
        ax.grid(alpha=0.3)
    axes[0].set_title("Parse, pipeline and full run vs data size")
    axes[1].set_title("COPY, index build and ANALYZE vs data size")
    fig.tight_layout()
    fig.savefig(out / "time_vs_size.png", dpi=130)
    plt.close(fig)


def query_modes(s, out):
    """Left: the mean over the 5 conditions per size. Middle: each condition at the largest size.
    Right: the drill-down with and without the index. Log scale: ms against seconds."""
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))
    per_mode = {m: [pick(s, f"query_drugs_for_condition_{m}_{c}", "ms") for c in CONDITIONS] for m, _ in MODES}
    sizes = list(per_mode["with_index"][0].index)
    # Mean of the 5 condition means (each condition counts once, whatever its number of matches).
    means = [pd.concat([d["mean"] for d in per_mode[m]], axis=1).mean(axis=1).loc[sizes] for m, _ in MODES]
    bars(axes[0], sizes, [label for _, label in MODES], means, legend=False)
    axes[0].set_xlabel("data size (share of the usable labels)")
    axes[0].set_title("drugs_for_condition: mean over the 5 conditions")
    largest = sizes[-1]
    values = [[d.loc[largest, "mean"] for d in per_mode[m]] for m, _ in MODES]
    errors = [[[d.loc[largest, "mean"] - d.loc[largest, "min"] for d in per_mode[m]],
               [d.loc[largest, "max"] - d.loc[largest, "mean"] for d in per_mode[m]]] for m, _ in MODES]
    bars(axes[1], CONDITIONS, [label for _, label in MODES], values, errors, legend=False)
    axes[1].set_xlabel(f"condition, at {largest}")
    axes[1].set_title(f"drugs_for_condition per condition ({largest})")
    w = pick(s, "query_labels_for_drug_with_index", "ms")
    wo = pick(s, "query_labels_for_drug_without_index", "ms")
    bars(axes[2], sizes, ["with GIN index", "without index"], [w["mean"], wo["mean"]], [minmax(w), minmax(wo)])
    axes[2].set_xlabel("data size (share of the usable labels)")
    axes[2].set_title("labels_for_drug (migraine, top ingredient)")
    for ax in axes:
        ax.set_yscale("log")
        ax.set_ylabel("query time (ms), log scale")
        ax.grid(alpha=0.3, axis="y")
    # One legend for the two left panels, below the figure, so it covers no bar.
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=3, fontsize=8, frameon=False)
    fig.suptitle("Mean of runs (with/without index: runs x 3 repetitions; on the fly: runs x 1); error bars min-max",
                 fontsize=9)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(out / "query_modes.png", dpi=130)
    plt.close(fig)


def disk(s, out):
    series = [("raw_zip", "14 zip files (read by a parse, at every size)"), ("raw_json", "JSON inside the zips"),
              ("kept_indications_text", "kept indications text"), ("disk_database", "whole database"),
              ("disk_labels_table", "labels heap"), ("disk_labels_toast", "labels TOAST (+ maps)"),
              ("disk_labels_gin_index", "GIN index")]
    data = [(label, pick(s, step, "MB")) for step, label in series]
    data = [(label, d) for label, d in data if not d.empty]
    fig, ax = plt.subplots(figsize=(11, 4.8))
    bars(ax, list(data[0][1].index), [label for label, _ in data], [d["mean"] for _, d in data])
    ax.set_yscale("log")                  # 8,750 MB of JSON next to a few MB of index
    ax.set_xlabel("data size (share of the usable labels)")
    ax.set_ylabel("size (MB), log scale")
    ax.set_title("Raw input vs database on disk")
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(out / "disk_db_vs_raw.png", dpi=130)
    plt.close(fig)


def memory(s, out):
    series = [(f"peak_mem_{c}_full_run", f"{c} (full run, load)") for c in ("db", "loader", "app")]
    series += [("peak_mem_db_queries", "db (query benchmark)"),
               ("peak_mem_loader_queries", "bench_queries.py client (loader image)")]
    data = [(label, pick(s, step, "MiB")) for step, label in series]
    data = [(label, d) for label, d in data if not d.empty]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars(ax, list(data[0][1].index), [label for label, _ in data], [d["mean"] for _, d in data],
         [minmax(d) for _, d in data])
    ax.set_xlabel("data size (share of the usable labels)")
    ax.set_ylabel("peak memory (MiB), docker stats")
    ax.set_title("Peak memory per container")
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(out / "memory_peak.png", dpi=130)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", default=str(ROOT / "measure" / "results"), help="folder with summary.csv")
    out = Path(p.parse_args().results)
    s = pd.read_csv(out / "summary.csv")
    time_vs_size(s, out)
    query_modes(s, out)
    disk(s, out)
    memory(s, out)
    print("written:", ", ".join(f"{out / n}.png" for n in ["time_vs_size", "query_modes", "disk_db_vs_raw", "memory_peak"]))


if __name__ == "__main__":
    main()
