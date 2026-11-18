# Parallel scan: why the query without the index runs with no worker, 100%, one load (`measure/parallel_scan.sh`)

**The question** (raised while reading the benchmark plans): in the benchmark's plans, the migraine query without the GIN index is a plain `Seq Scan` with no worker, while the on-the-fly query uses 2 workers. Why, and is the index's speed-up measured from Python the speed-up the database sees?

**What changed, one thing:** the planner's three parallel cost settings, for one session only: `SET parallel_setup_cost = 0, parallel_tuple_cost = 0, min_parallel_table_scan_size = 0` (`measure/parallel_scan.py`, `PARALLEL`). The data, the query and the server settings stay as they are. For the estimates only, each of the three is also set to 0 alone, to see which one decides.

**Protocol** (`run.txt`, first and last line: 17:45:26-17:45:51 UTC on 5 Nov 2026, commit `ca5f98e`, compose project `de-exp`):
- One fresh volume, one load at 100% from the extract (78,472 labels, 8,157 drugs), with the v2 defaults.
- `parallel_scan.py` in the loader image prints the planner's inputs (`SHOW`, `pg_class`, `pg_proc`), then `EXPLAIN` (estimates only) of the migraine query without the index under each setting, and the on-the-fly query with and without workers (`max_parallel_workers_per_gather = 0`).
- Timed: rounds in the order D P P D D P (D = default settings, P = the three at 0). Each round has 1 untimed warm-up, 3 timed executions from Python (what a client waits) and 1 `EXPLAIN (ANALYZE, BUFFERS)` (what the database spends). Then the index is built again, and 3 rounds with the index, default settings.
- `stats.txt` is written by `measure/parallel_scan_summary.py` from `run.txt`.

**What the planner knows** (`run.txt`, lines 6-29): `labels` has 8,768 pages (`relpages`) and 78,472 rows, a 71,827,456-byte heap. Its TOAST table has 0 pages in `pg_class` (`reltuples` −1), although it holds 39,911,424 bytes. `parallel_setup_cost` 1000, `parallel_tuple_cost` 0.1, `min_parallel_table_scan_size` 8MB, `max_parallel_workers_per_gather` 2; `ts_match_vq` costs 1 × `cpu_operator_cost` per row, `to_tsvector` 100 ×.

**The estimates** (cost units, `run.txt`, the `estimate_*` rows):

| Setting changed | Whole plan | Workers planned | Scan node |
|---|---:|---:|---:|
| none (default) | 10,015.70 | 0 | 9,748.90 |
| `parallel_setup_cost = 0` | 9,487.51 | 2 | 9,176.71 |
| `parallel_tuple_cost = 0` | 10,015.70 | 0 | 9,748.90 |
| `min_parallel_table_scan_size = 0` | 10,015.70 | 0 | 9,748.90 |
| setup and tuple cost 0 | 9,430.16 | 2 | 9,176.71 |
| all three 0 | 9,430.16 | 2 | 9,176.71 |
| on the fly, default | 18,619.36 | 2 | 17,350.88 |
| on the fly, no workers | 29,607.74 | 0 | 29,366.90 |

**Timed** (`stats.txt`; ms, mean (min-max); client n = 9, database n = 3):

| Query | Client (Python) | Database (`Execution Time`) |
|---|---:|---:|
| without the index, default | 90.20 (73.92-118.54) | 82.13 (69.66-90.57) |
| without the index, the three at 0 | 43.97 (36.60-54.36) | 46.80 (36.63-53.22) |
| with the index, default | 1.94 (1.42-2.27) | 1.77 (1.35-2.03) |

The forced plans launched 2 workers in every P round; the default plans launched 0 (`run.txt`, "workers launched").

**What it means** (arithmetic on the rows above):
- Only `parallel_setup_cost` keeps the workers out. With it at 0 the parallel plan costs 9,487.51. The setup cost of 1000 put back gives 10,487.51, more than the serial 10,015.70, so the planner picks the serial plan.
- Workers save the scan only 572.19 units (9,748.90 − 9,176.71), because the disk part of the estimate, 8,768 pages × `seq_page_cost` 1, is not divided among workers; only the CPU part, 78,472 rows × (0.01 + 0.0025) = 980.90, is. On the fly, `to_tsvector` costs 100 × `cpu_operator_cost` per row, so the CPU part is large and workers save 12,016.02 units (29,366.90 − 17,350.88): the planner uses them.
- The planner prices the 8,768 heap pages but sees 0 pages of TOAST, where the long texts are. Judgement, not checked: the serial plan may look cheaper than it is.
- Forced workers make the scan 1.76 times faster inside the database and 2.05 times faster from Python, with 2 workers plus the leader. The index makes the query 46.50 times faster inside the database and 46.52 times faster from Python in this run (`stats.txt`), so here the two views agree. The user waits for the Python time, round trip included.
- Decision: the settings stay at the defaults (`docs/decision_log.md` D-35). The index removes the scan, and these are server-wide settings for a path the app does not take (Judgement).

**The course on this:** : "Amdahl’s law: the serial part wins. Speedup = 1 / ((1 − p) + p / N), with p the parallel fraction and N the workers. As N grows, only 1 − p matters." Judgement: the planner reasons the same way here. Reading the 8,768 pages is the part it does not share among workers (9,176.71 − 8,768 = 408.71 units are left of the CPU part's 980.90, arithmetic), so 2 workers would save it little. (Appendix H1): "Measure before you buy. The bottleneck is rarely the part you suspected."
