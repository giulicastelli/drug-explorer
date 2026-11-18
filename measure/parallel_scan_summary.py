"""Means of the timed rows of measure/results_experiments/parallel_scan/run.txt (parallel_scan.sh).
client_ms = Python, 1 warm-up + 3 timed per round; db_ms = EXPLAIN ANALYZE Execution Time, 1 per round.
Standard library only:  python3 measure/parallel_scan_summary.py > measure/results_experiments/parallel_scan/stats.txt
"""
import statistics as s
from collections import defaultdict
from pathlib import Path

d = defaultdict(list)
for line in (Path(__file__).resolve().parent / "results_experiments" / "parallel_scan" / "run.txt").open():
    if line.startswith(("ROW,client_ms", "ROW,db_ms")):
        p = line.split(",")
        d[p[1]].append(float(p[2]))
print("step, n, mean, min, max, median (ms)")
for k, v in d.items():
    print(f"{k}, {len(v)}, {s.mean(v):.2f}, {min(v):.2f}, {max(v):.2f}, {s.median(v):.2f}")
m = {k: s.mean(v) for k, v in d.items()}
for what, a, b in [("parallel settings, without the index", "without_index_default", "without_index_parallel_settings"),
                   ("the index (default settings)", "without_index_default", "with_index_default")]:
    print(f"speed-up of {what}: client {m['client_ms_' + a] / m['client_ms_' + b]:.2f}x, "
          f"in the database {m['db_ms_' + a] / m['db_ms_' + b]:.2f}x")
