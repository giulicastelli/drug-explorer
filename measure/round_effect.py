"""Round effect in benchmark v1 (from our first round of checks): round 1 was the slowest run
at every size. Does the interleaving cancel it across sizes, and what is left of the growth
with the size once each size is compared inside its own round?

Reads only the v1 results, which stay unchanged (they are the "before"):
    measure/results/raw_runs.csv      the values (column "run" = the round: one run of every size per round)
    measure/results/benchmark_log.txt the order the runs started in, with the clock time
Standard library only. Run from the repository root:
    python3 measure/round_effect.py > measure/results_experiments/round_effect/output.txt
Writes measure/results_experiments/round_effect/by_round.csv as well.
"""
import csv
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "measure" / "results"
OUT = ROOT / "measure" / "results_experiments" / "round_effect"
SIZES, ROUNDS, STEPS = ["25%", "50%", "100%"], ["1", "2", "3"], ["full_run", "parse", "copy"]


def main():
    # values[(mode, step, size, round)]; mode is the last word of the environment column
    values = {}
    with open(RESULTS / "raw_runs.csv", newline="") as f:
        for r in csv.DictReader(f):
            mode = r["environment"].rsplit("mode=", 1)[1]
            values[(mode, r["step"], r["size"], r["run"])] = float(r["value"])

    # The order of the runs: "[bench 15:06:00] === size 25%, run 1, mode generated (...) ==="
    order = re.findall(r"\[bench (\d\d:\d\d:\d\d)\] === size (\d+%), run (\d), mode (\w+)",
                       (RESULTS / "benchmark_log.txt").read_text())
    print("Run order (benchmark_log.txt), position in its round, load average before it (raw_runs.csv):")
    position = {}
    for clock, size, rnd, mode in order:
        position[(size, rnd, mode)] = sum(1 for k in position if k[1] == rnd) + 1
        load = values[(mode, "machine_load_1min", size, rnd)]
        print(f"  {clock}  round {rnd}  position {position[(size, rnd, mode)]}  {size:>4} {mode:9}  load {load:.2f}")

    rows = []
    for step in STEPS:
        print(f"\n{step} (s), mode generated: one value per (size, round)")
        print("| size | round 1 | round 2 | round 3 | mean (v1) | mean of rounds 2-3 | round 1 minus mean of 2-3 |")
        print("|---|---|---|---|---|---|---|")
        for size in SIZES:
            v = [values[("generated", step, size, r)] for r in ROUNDS]
            rest = statistics.mean(v[1:])
            print(f"| {size} | {v[0]:.2f} | {v[1]:.2f} | {v[2]:.2f} | {statistics.mean(v):.2f} | {rest:.2f} | {v[0] - rest:+.2f} |")
            rows += [[step, size, r, f"{x:.3f}", position[(size, r, 'generated')]] for r, x in zip(ROUNDS, v)]
        means = [statistics.mean(values[("generated", step, s, r)] for s in SIZES) for r in ROUNDS]
        print("| round mean over the 3 sizes | " + " | ".join(f"{m:.2f}" for m in means) + " | | | |")

        # Two-way split: value = grand mean + size effect + round effect + rest. Each size has exactly
        # one run in each round (and each position once), so a round effect adds the same amount to
        # every size's mean: it cancels in the comparison between sizes, but it is in each size's std.
        grand = statistics.mean(values[("generated", step, s, r)] for s in SIZES for r in ROUNDS)
        size_eff = {s: statistics.mean(values[("generated", step, s, r)] for r in ROUNDS) - grand for s in SIZES}
        round_eff = {r: m - grand for r, m in zip(ROUNDS, means)}
        rest = {(s, r): values[("generated", step, s, r)] - grand - size_eff[s] - round_eff[r] for s in SIZES for r in ROUNDS}
        print(f"grand mean {grand:.2f} s; size effect " + ", ".join(f"{s} {size_eff[s]:+.2f}" for s in SIZES)
              + "; round effect " + ", ".join(f"r{r} {round_eff[r]:+.2f}" for r in ROUNDS))
        for s in SIZES:
            v = [values[("generated", step, s, r)] for r in ROUNDS]
            left = [values[("generated", step, s, r)] - round_eff[r] for r in ROUNDS]
            print(f"  {s}: std of the 3 runs {statistics.stdev(v):.2f} s; after removing the round effect {statistics.stdev(left):.2f} s")
        print("growth inside each round (same round, so the same round effect):")
        for r in ROUNDS:
            a, b, c = (values[("generated", step, s, r)] for s in SIZES)
            print(f"  round {r}: 25%->50% {100 * (b / a - 1):+.1f}%, 50%->100% {100 * (c / b - 1):+.1f}%, 25%->100% {100 * (c / a - 1):+.1f}%")
        a, c = (statistics.mean(values[("generated", step, s, r)] for r in ROUNDS) for s in ("25%", "100%"))
        print(f"  means (all rounds): 25%->100% {100 * (c / a - 1):+.1f}%")

    # The tsv-after run is always the 4th and last of its round, at 25%: a fifth view of the drift.
    print("\nparse at 25% in the tsv-after runs (position 4 of each round): "
          + ", ".join(f"round {r} {values[('after', 'parse', '25%', r)]:.2f} s" for r in ROUNDS))

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "by_round.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["step", "size", "round", "seconds", "position_in_round"])
        w.writerows(rows)


if __name__ == "__main__":
    main()
