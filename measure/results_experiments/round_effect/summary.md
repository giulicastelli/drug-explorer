# Round effect in benchmark v1: one value per (size, round) (`measure/round_effect.py`)

**The question** (from our first round of checks): in benchmark v1, round 1 was the slowest run at every size. Does the interleaving cancel it across sizes, and what is left of the growth with the size once each size is compared inside its own round?

**What changed, one thing:** the grouping, not the system. Nothing was run again. The script takes v1's raw values and lays them out by round (one run of every size per round) instead of averaging the 3 runs of each size. v1 stays unchanged: it is the "before".

**Protocol:** `round_effect.py` reads `measure/results/raw_runs.csv` (the values; its column `run` is the round) and `measure/results/benchmark_log.txt` (the order the runs started in, with the clock time), with Python's standard library only. It writes `output.txt` and `by_round.csv` (committed in `8de5e1e`). Steps: `full_run`, `parse` and `copy`, mode `generated`. The effects in `output.txt` are a two-way split: grand mean, plus a size effect, plus a round effect.

**The v1 schedule** (`output.txt`): 12 runs on 5 Nov 2026, started from 15:06:00 to 15:25:49 UTC, the sizes rotated in each round (25-50-100, 50-100-25, 100-25-50), each round ending with the 25% `--extra-tsv-after` run. The load average before a run ranged from 0.21 (round 1, 25%) to 3.49 (round 3, 50%).

**Results** (`output.txt`, s):

| Step | Size | Round 1 | Round 2 | Round 3 | Round 1 minus the mean of rounds 2-3 | std of the 3 runs | std without the round effect |
|---|---|---:|---:|---:|---:|---:|---:|
| `parse` | 25% | 67.44 | 58.68 | 63.83 | +6.18 | 4.40 | 2.34 |
| `parse` | 50% | 71.44 | 64.79 | 63.34 | +7.37 | 4.32 | 1.08 |
| `parse` | 100% | 71.57 | 66.47 | 64.26 | +6.20 | 3.75 | 1.37 |
| `full_run` | 25% | 78.97 | 69.68 | 74.38 | +6.94 | 4.64 | 2.47 |
| `full_run` | 50% | 86.80 | 79.85 | 78.40 | +7.67 | 4.49 | 0.67 |
| `full_run` | 100% | 95.69 | 88.57 | 84.95 | +8.94 | 5.47 | 1.86 |
| `copy` | 25% | 3.14 | 2.88 | 2.79 | +0.30 | 0.18 | 0.37 |
| `copy` | 50% | 6.26 | 6.01 | 6.18 | +0.16 | 0.13 | 0.51 |
| `copy` | 100% | 13.33 | 11.72 | 10.50 | +2.22 | 1.42 | 0.87 |

Round effects over the 3 sizes: `parse` +4.39 / −2.44 / −1.95 s, `full_run` +5.23 / −2.55 / −2.68 s, `copy` +0.60 / −0.11 / −0.49 s. Growth from 25% to 100% inside one round: `parse` +6.1% / +13.3% / +0.7%; `full_run` +21.2% / +27.1% / +14.2%; `copy` +324.7% / +306.6% / +276.6%.

**What it means:**
- Round 1 is slower at every size, by about 6-7 s of `parse`, and `parse` is most of it. `copy` is barely affected, except +2.22 s at 100%.
- The size comparison holds: each size ran once in each round and once in each position, so round 1 is inside every size's mean exactly once.
- The spread of `parse` and `full_run` is mostly this effect: taking it out lowers the `parse` std from 3.75-4.40 s to 1.08-2.34 s.
- Inside one round `parse` stays nearly flat, +0.7% to +13.3% from 25% to 100%, because every size reads all 14 zips (`docs/decision_log.md` D-3). `copy` grows about 4 times for 4 times the rows.
- The cause is unknown on the shared VM. Round 1 at 25% had the lowest load average, 0.21, and was still the slowest 25% run. Every run is reported; none was dropped (D-37).
- In v2 (another folder, by arithmetic on `measure/results_v2/raw_runs.csv`, D-52) the slowest runs were the first run of the whole benchmark (25%, round 1: COPY 3.56 s against 2.52 and 2.74 s) and the first of the 3 first starts (83.15 s against 80.97 and 80.32 s), not round 1 at every size. Benchmark v3 predicts it again (`measure/predictions_v3.md`, Q28).

**The course on this:** : "MEASURE FAIRLY: Run each test 3 times, report the average. Write down the laptop: processor and RAM. Change one thing at a time." The interleaving is what lets the average of 3 stay fair when one round is slower for a reason outside the code.
