"""Summary of measure/results_experiments/gin_expression/runs.txt (written by gin_expression.sh).
Mean, min and max over the 3 loads of each (size, mode); query times pool 3 loads x 3 reps.
Also writes the plans of the first load of each (size, mode) to explain/<size>_<mode>_<condition>.txt.
Standard library only:  python3 measure/gin_expression_summary.py > measure/results_experiments/gin_expression/summary_table.txt
"""
import re
import statistics
from collections import defaultdict
from pathlib import Path

DIR = Path(__file__).resolve().parent / "results_experiments" / "gin_expression"
text = (DIR / "runs.txt").read_text()

values, details = defaultdict(list), defaultdict(set)
for line in text.splitlines():
    if line.startswith("ROW,"):
        _, size, mode, load, step, value, unit, *detail = line.split(",")
        try:
            values[(size, mode, step)].append((float(value), unit))
        except ValueError:
            pass
        details[(size, mode, step)].add(",".join(detail) if "answer" in step or "index_def" in step else "")

for size in ("0.25", "1.0"):
    print(f"\n## {float(size):.0%}: mean (min-max) of the loads; queries: 3 loads x 3 reps")
    print("| step | generated (A) | expression (B) | B / A |")
    print("|---|---|---|---|")
    steps = sorted({k[2] for k in values if k[0] == size}, key=lambda s: (not s.startswith("disk"), s))
    for step in steps:
        cells, means = [], []
        for mode in ("generated", "expression"):
            v = values.get((size, mode, step))
            if not v:
                cells.append("-"), means.append(None)
                continue
            nums, unit = [x for x, _ in v], v[0][1]
            means.append(statistics.mean(nums))
            cells.append(f"{statistics.mean(nums):,.3f} ({min(nums):,.3f}-{max(nums):,.3f}) {unit}, n={len(nums)}")
        ratio = f"{means[1] / means[0]:.2f}" if None not in means and means[0] else ""
        print(f"| {step} | {cells[0]} | {cells[1]} | {ratio} |")
    for mode in ("generated", "expression"):
        for step in ("answer_migraine", "answer_type_2_diabetes", "index_definition"):
            print(f"{mode} {step}: {sorted(details[(size, mode, step)])}")

# the plans of load 1 (generated) and load 2 (expression) at each size
out = DIR / "explain"
out.mkdir(exist_ok=True)
size = None
for block in re.split(r"(?m)^# load ", text)[1:]:
    head = block.splitlines()[0]
    n, size, mode = re.match(r"(\d): size=([\d.]+) mode=(\w+)", head).groups()
    if n not in ("1", "2"):
        continue
    for cond, plan in re.findall(r"----- BEGIN EXPLAIN drugs_for_condition (.+?) \(\w+\) -----\n(.*?)----- END EXPLAIN -----",
                                 block, re.S):
        (out / f"{float(size):.0%}_{mode}_{cond.replace(' ', '_')}.txt".replace("%", "pct")).write_text(plan)
print(f"\nplans written to {out}")
