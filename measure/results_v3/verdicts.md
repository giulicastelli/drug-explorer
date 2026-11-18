# Benchmark v3: each prediction against the result

**Order.** `measure/predictions_v3.md` was committed at **20:27:31 UTC** on 5 Nov 2026 (`dcbefbf`, `git log -1 --format=%ci dcbefbf`). The benchmark started at **20:27:50 UTC** (first line of `benchmark_log.txt`), its first run at 20:27:53, and it finished at 20:45:42 (1071 s for 12 runs; v2 took 1019 s). Protocol: `python3 measure/benchmark.py --drop-caches --first-start 3 --out measure/results_v3`, the same as v2, on `add-benchmark-v3` at `dcbefbf` (loader code of merge `7032f94`; `benchmark.py` of `d794808`). Machine, Docker and the `postgres:16` and `python:3.12-slim` image ids are the same as v2's (`machine.txt`); the loader image was rebuilt (new code). Only this project's containers ran (`docker ps` empty before the start); `os_cache_dropped` = 1 in all 12 runs.

**Rule (`measure/README.md`, line 13, "Prediction verdicts, one rule"):** gap = (measured − predicted) / predicted. |gap| ≤ 10% is confirmed, ≤ 25% is close, anything else is missed. "In range" (extra, not part of the rule) says whether the v3 mean fell in the range written in `predictions_v3.md`. Every gap below is arithmetic on `measure/results_v3/summary.csv`.

## Tally

- **64 values under the rule: 51 confirmed, 11 close, 2 missed.** 58 of the 64 means fell inside the written range (arithmetic).
- **Known before** (`predictions_v3.md`): every row had a v2 value on the same protocol, so matching it shows that the run repeats, not that the model of the pipeline is right. 13 rows also had a v3-code value before the prediction (`v2+v3ev`: later starts at 100%, rows and extract size): 11 confirmed, 2 close. The other 50 rows had no v3-code value: 39 confirmed, 9 close, 2 missed. The two rows with nothing behind them, Q26 and Q27 (`docker_stats_samples.csv`), are right: 0 duplicate rows, 1,487 rows against 1,400 predicted (+6.2%, confirmed).
- Q28 (run 1 of the 25% series has the longest `full_run`): **yes**, 12.18 s against 11.76 and 11.84 s (`raw_runs.csv`). Run 1 was also the longest at 50% (17.30 s) and 100% (23.18 s), but not among the first starts (90.35 s was run 3).

## Every prediction

| # | Step | Size | Mode | v2 mean | Predicted (range) | v3 mean (min-max) | Gap | In range | Verdict | Known before |
|---|---|---|---|---:|---:|---:|---:|---|---|---|
| Q1 | `download` (s) | 25% | generated | 0.0127 | 0.007 (0.004-0.012) | 0.0077 (0.0067-0.0094) | +10.0% | yes | confirmed | v2 |
| Q1 | `download` (s) | 50% | generated | 0.0107 | 0.007 (0.004-0.012) | 0.0084 (0.007-0.0102) | +20.0% | yes | close | v2 |
| Q1 | `download` (s) | 100% | generated | 0.0116 | 0.007 (0.004-0.012) | 0.0076 (0.006-0.0102) | +8.6% | yes | confirmed | v2+v3ev |
| Q2 | `read_extract` (s) | 25% | generated | 1.005 | 1 (0.85-1.25) | 1.055 (1.013-1.105) | +5.5% | yes | confirmed | v2 |
| Q2 | `read_extract` (s) | 50% | generated | 1.104 | 1.1 (0.95-1.35) | 1.268 (1.118-1.455) | +15.2% | yes | close | v2 |
| Q2 | `read_extract` (s) | 100% | generated | 1.249 | 1.3 (1.1-1.7) | 1.29 (1.143-1.438) | -0.8% | yes | confirmed | v2+v3ev |
| Q3 | `copy` (s) | 25% | generated | 2.943 | 3 (2.5-3.7) | 2.679 (2.616-2.712) | -10.7% | yes | close | v2 |
| Q3 | `copy` (s) | 50% | generated | 5.259 | 5.5 (5-6.2) | 5.782 (5.524-6.258) | +5.1% | yes | confirmed | v2 |
| Q3 | `copy` (s) | 100% | generated | 10.62 | 11.2 (10.4-12.6) | 10.9 (10.21-11.43) | -2.7% | yes | confirmed | v2+v3ev |
| Q4 | `index_build` (s) | 25% | generated | 0.307 | 0.31 (0.26-0.4) | 0.335 (0.3041-0.3751) | +8.1% | yes | confirmed | v2 |
| Q4 | `index_build` (s) | 50% | generated | 0.6722 | 0.67 (0.55-0.8) | 0.7267 (0.6734-0.7808) | +8.5% | yes | confirmed | v2 |
| Q4 | `index_build` (s) | 100% | generated | 1.31 | 1.4 (1.25-1.75) | 1.559 (1.443-1.78) | +11.4% | yes | close | v2+v3ev |
| Q5 | `build_drugs` (s) | 25% | generated | 0.0486 | 0.05 (0.04-0.07) | 0.0565 (0.0506-0.0674) | +13.0% | yes | close | v2 |
| Q5 | `build_drugs` (s) | 50% | generated | 0.1195 | 0.12 (0.08-0.17) | 0.1399 (0.0918-0.1864) | +16.6% | yes | close | v2 |
| Q5 | `build_drugs` (s) | 100% | generated | 0.2113 | 0.22 (0.18-0.27) | 0.268 (0.2502-0.2873) | +21.8% | yes | close | v2+v3ev |
| Q6 | `analyze` (s) | 25% | generated | 0.519 | 0.52 (0.45-0.65) | 0.5672 (0.4849-0.7118) | +9.1% | yes | confirmed | v2 |
| Q6 | `analyze` (s) | 50% | generated | 0.9388 | 0.94 (0.85-1.1) | 0.9412 (0.8976-1.008) | +0.1% | yes | confirmed | v2 |
| Q6 | `analyze` (s) | 100% | generated | 0.9617 | 1.05 (0.9-1.4) | 1.046 (0.9615-1.094) | -0.3% | yes | confirmed | v2+v3ev |
| Q7 | `pipeline_total` (s) | 25% | generated | 4.892 | 5 (4.4-5.8) | 4.767 (4.699-4.867) | -4.7% | yes | confirmed | v2 |
| Q7 | `pipeline_total` (s) | 50% | generated | 8.162 | 8.4 (7.6-9.3) | 8.946 (8.376-9.694) | +6.5% | yes | confirmed | v2 |
| Q7 | `pipeline_total` (s) | 100% | generated | 14.44 | 15.2 (14.2-16.9) | 15.17 (14.29-15.79) | -0.2% | yes | confirmed | v2+v3ev |
| Q8 | `full_run` (s) | 25% | generated | 11.71 | 11.9 (11-12.8) | 11.93 (11.76-12.18) | +0.2% | yes | confirmed | v2 |
| Q8 | `full_run` (s) | 50% | generated | 14.82 | 15.3 (14.1-16.3) | 16.3 (15.55-17.3) | +6.5% | yes | confirmed | v2 |
| Q8 | `full_run` (s) | 100% | generated | 21.32 | 22.1 (20.8-24) | 22.37 (21.36-23.18) | +1.2% | yes | confirmed | v2+v3ev |
| Q9 | `download` (s) | 100% | first_start | 0.0127 | 0.013 (0.009-0.02) | 0.0142 (0.0123-0.0155) | +9.2% | yes | confirmed | v2 |
| Q10 | `parse` (s) | 100% | first_start | 59.07 | 59.1 (57.5-62) | 64.09 (61.93-67.35) | +8.4% | no | confirmed | v2 |
| Q11 | `write_extract` (s) | 100% | first_start | 1.451 | 1.45 (1.3-1.7) | 1.389 (1.326-1.427) | -4.2% | yes | confirmed | v2 |
| Q12 | `pipeline_total` (s) | 100% | first_start | 74.61 | 74.7 (72.5-77.5) | 80.21 (78.54-83.13) | +7.4% | no | confirmed | v2 |
| Q13 | `full_run` (s) | 100% | first_start | 81.48 | 81.6 (79-84.5) | 87.44 (85.75-90.35) | +7.2% | no | confirmed | v2 |
| Q14 | `query_drugs_for_condition_with_index_migraine` (ms) | 25% | generated | 1.954 | 1.8 (1.2-2.8) | 1.98 (1.473-2.6) | +10.0% | yes | close | v2 |
| Q14 | `query_drugs_for_condition_with_index_migraine` (ms) | 50% | generated | 1.695 | 1.8 (1.2-2.8) | 1.265 (1.021-1.619) | -29.7% | yes | missed | v2 |
| Q14 | `query_drugs_for_condition_with_index_migraine` (ms) | 100% | generated | 1.68 | 1.8 (1.2-2.8) | 3.218 (1.941-6.304) | +78.8% | no | missed | v2 |
| Q15 | `query_drugs_for_condition_without_index_migraine` (ms) | 25% | generated | 20.69 | 21 (18-26) | 21.12 (19.43-23.67) | +0.6% | yes | confirmed | v2 |
| Q15 | `query_drugs_for_condition_without_index_migraine` (ms) | 50% | generated | 51.19 | 50 (38-64) | 56.89 (37.27-78.7) | +13.8% | yes | close | v2 |
| Q15 | `query_drugs_for_condition_without_index_migraine` (ms) | 100% | generated | 83.61 | 84 (72-105) | 82.34 (72.51-105.8) | -2.0% | yes | confirmed | v2 |
| Q16 | `query_drugs_for_condition_on_the_fly_migraine` (ms) | 25% | generated | 1,156 | 1,150 (1,050-1,300) | 1,175 (1,110-1,239) | +2.2% | yes | confirmed | v2 |
| Q16 | `query_drugs_for_condition_on_the_fly_migraine` (ms) | 50% | generated | 1,464 | 1,480 (1,350-1,650) | 1,793 (1,616-2,060) | +21.2% | no | close | v2 |
| Q16 | `query_drugs_for_condition_on_the_fly_migraine` (ms) | 100% | generated | 2,998 | 3,000 (2,800-3,300) | 3,214 (3,102-3,281) | +7.1% | yes | confirmed | v2 |
| Q17 | `rows_loaded` (rows) | 25% | generated | 1.955e+04 | 1.955e+04 (1.955e+04-1.955e+04) | 1.955e+04 (1.955e+04-1.955e+04) | +0.0% | yes | confirmed | v2+v3ev |
| Q17 | `rows_loaded` (rows) | 50% | generated | 3.904e+04 | 3.904e+04 (3.904e+04-3.904e+04) | 3.904e+04 (3.904e+04-3.904e+04) | +0.0% | yes | confirmed | v2 |
| Q17 | `rows_loaded` (rows) | 100% | generated | 7.847e+04 | 7.847e+04 (7.847e+04-7.847e+04) | 7.847e+04 (7.847e+04-7.847e+04) | +0.0% | yes | confirmed | v2+v3ev |
| Q18 | `disk_database` (MB) | 25% | generated | 41.3 | 41.3 (41.25-41.35) | 41.3 (41.3-41.3) | +0.0% | yes | confirmed | v2 |
| Q18 | `disk_database` (MB) | 50% | generated | 73.78 | 73.78 (73.73-73.83) | 73.78 (73.78-73.78) | +0.0% | yes | confirmed | v2 |
| Q18 | `disk_database` (MB) | 100% | generated | 138.3 | 138.3 (138.3-138.4) | 138.3 (138.3-138.3) | -0.0% | yes | confirmed | v2 |
| Q19 | `disk_database` (MB) | 100% | first_start | 138.1 | 138.1 (138.1-138.2) | 138.1 (138.1-138.1) | +0.0% | yes | confirmed | v2 |
| Q20 | `extract_csv` (bytes) | 25% | generated | 74,388,073 | 74,388,073 (74,388,073-74,388,073) | 74,388,073 (74,388,073-74,388,073) | +0.0% | yes | confirmed | v2+v3ev |
| Q20 | `extract_csv` (bytes) | 50% | generated | 74,388,073 | 74,388,073 (74,388,073-74,388,073) | 74,388,073 (74,388,073-74,388,073) | +0.0% | yes | confirmed | v2+v3ev |
| Q20 | `extract_csv` (bytes) | 100% | generated | 74,388,073 | 74,388,073 (74,388,073-74,388,073) | 74,388,073 (74,388,073-74,388,073) | +0.0% | yes | confirmed | v2+v3ev |
| Q21 | `peak_mem_loader_full_run` (MiB) | 25% | generated | 83.49 | 84 (79-88) | 82.52 (81.86-83.6) | -1.8% | yes | confirmed | v2 |
| Q21 | `peak_mem_loader_full_run` (MiB) | 50% | generated | 140.1 | 140 (133-147) | 140.8 (140.6-141.1) | +0.5% | yes | confirmed | v2 |
| Q21 | `peak_mem_loader_full_run` (MiB) | 100% | generated | 257.4 | 257 (245-270) | 257.4 (257.2-257.8) | +0.2% | yes | confirmed | v2 |
| Q22 | `peak_mem_db_full_run` (MiB) | 25% | generated | 122.4 | 122 (115-130) | 98.71 (98.3-99.51) | -19.1% | no | close | v2 |
| Q22 | `peak_mem_db_full_run` (MiB) | 50% | generated | 169 | 169 (160-178) | 168.6 (168.3-169) | -0.3% | yes | confirmed | v2 |
| Q22 | `peak_mem_db_full_run` (MiB) | 100% | generated | 234.5 | 235 (222-248) | 234.7 (234-235) | -0.1% | yes | confirmed | v2 |
| Q23 | `peak_mem_db_queries` (MiB) | 25% | generated | 101.8 | 102 (90-117) | 101.5 (101.4-101.7) | -0.5% | yes | confirmed | v2 |
| Q23 | `peak_mem_db_queries` (MiB) | 50% | generated | 189.1 | 189 (165-215) | 188.8 (186.7-190.1) | -0.1% | yes | confirmed | v2 |
| Q23 | `peak_mem_db_queries` (MiB) | 100% | generated | 269.2 | 269 (235-300) | 269.2 (246.9-280.7) | +0.1% | yes | confirmed | v2 |
| Q24 | `peak_mem_app_full_run` (MiB) | 25% | generated | 52.88 | 52.8 (50-56) | 53.1 (52.89-53.33) | +0.6% | yes | confirmed | v2 |
| Q24 | `peak_mem_app_full_run` (MiB) | 50% | generated | 52.78 | 52.8 (50-56) | 52.96 (52.86-53.12) | +0.3% | yes | confirmed | v2 |
| Q24 | `peak_mem_app_full_run` (MiB) | 100% | generated | 52.76 | 52.8 (50-56) | 53.11 (53.1-53.12) | +0.6% | yes | confirmed | v2 |
| Q25 | `peak_mem_loader_full_run` (MiB) | 100% | first_start | 258.9 | 259 (246-271.9) | 259 (257.7-261.3) | +0.0% | yes | confirmed | v2 |
| Q25 | `peak_mem_db_full_run` (MiB) | 100% | first_start | 237.4 | 237 (225.1-248.9) | 237.1 (236.7-237.6) | +0.0% | yes | confirmed | v2 |
| Q25 | `peak_mem_app_full_run` (MiB) | 100% | first_start | 52.74 | 52.7 (50.06-55.34) | 53.04 (52.89-53.11) | +0.6% | yes | confirmed | v2 |
| Q26 | `docker_stats_samples.csv` duplicate rows | all | all | 1,378 (2,791 − 1,413) | 0 | 0 | | yes | right | new |
| Q27 | `docker_stats_samples.csv` rows | all | all | 2,791 | 1,400 (1,150-1,700) | 1,487 | +6.2% | yes | confirmed | new |
| Q28 | run 1 longest `full_run` at 25% | 25% | generated | yes | yes | yes (12.18 vs 11.76 / 11.84 s) | | | right | v2 |

Q1 at 25% is on the boundary: 0.0077 / 0.007 − 1 = +10.0% (arithmetic), counted as confirmed because the rule says ≤ 10%.

## The two misses, and the surprises the predictions file named

- **Q14, migraine with the index, 50% (−29.7%) and 100% (+78.8%).** At 100% the per-run means are 2.95, 4.66 and 2.04 ms (the 9 values in `raw_runs.csv`, arithmetic); run 2's first repetition is 6.30 ms. The work in the database did not change: the plan in `explain/100pct_drugs_for_condition_with_index.txt` has the same `Buffers: shared hit=755` as v2's, and its Execution Time is 2.251 ms (v2 1.545 ms). Judgement: at 1-6 ms the time is mostly the Python round trip and the scheduler, and a 10% tolerance on a 1.8 ms value is narrower than this machine's noise. The prediction was wrong, and the range (1.2-2.8 ms) was too narrow at 100%.
- **Surprise named in advance: `parse` more than 5% away from 59.1 s.** It was 62.99 / 61.93 / 67.35 s, mean 64.09 s (+8.4%: confirmed under the rule, but outside the range 57.5-62.0 s and past the 5% line written as a surprise). The parse code did not change between v2 and v3 (`git diff b5ecc7c 7032f94 -- loader/load_fda.py` touches `download`, the extract name and `load_info`, not `parse`), the ijson backend is `yajl2_c` (`machine.txt`) and the load average after the settle was 1.02 / 0.82 / 0.82 (v2 first starts: 0.83 mean). What made it slower was not found. It is inside v1's parse range at 100% (67.43 s mean, `measure/results/summary.csv`). As a result, Q12 (`pipeline_total`, +7.4%) and Q13 (`full_run`, +7.2%) of the first start are confirmed under the rule but outside their ranges.
- Other rows outside the range: Q16 on the fly at 50% (1,793 ms, +21.2%, close) and Q22 db peak at 25% (98.7 MiB against 122, −19.1%, close). The db peak at 25% fell 23.7 MiB from v2 at the same size (arithmetic) with the same rows. Judgement: `docker stats` counts the page cache of what the container writes, and that is not under our control. The other sizes matched within 0.3%.
- Surprise "later start at 100% more than 10% faster than v2": no. It was 4.9% slower (22.37 vs 21.32 s, +1.05 s, arithmetic): `pipeline_total` +0.72 s (COPY +0.28 s, `index_build` +0.25 s, `analyze` +0.08 s, `read_extract` +0.04 s) and the fixed part (`full_run` − `pipeline_total`) +0.32 s, 7.20 s against 6.88 s.

## v2 → v3 at 100% (means from `results_v2/summary.csv` and `results_v3/summary.csv`)

| Value | v2 | v3 | Change (arithmetic) |
|---|---:|---:|---:|
| Later start `full_run` | 21.32 s | 22.37 s (21.36-23.18) | +4.9% |
| Later start `pipeline_total` | 14.44 s | 15.17 s | +5.0% |
| Later start `copy` | 10.62 s | 10.90 s | +2.6% |
| Later start `read_extract` | 1.25 s | 1.29 s | +3.3% |
| Later start `download` (v3: zips not checked) | 0.0116 s | 0.0076 s | −4 ms |
| First start `full_run` | 81.48 s | 87.44 s (85.75-90.35) | +7.3% |
| First start `parse` | 59.07 s | 64.09 s | +8.5% |
| Migraine, with the index | 1.68 ms | 3.22 ms | +92% |
| Migraine, without the index | 83.6 ms | 82.3 ms | −1.5% |
| Migraine, on the fly | 2,998 ms | 3,214 ms | +7.2% |
| Database | 138.31 MB | 138.30 MB | −0.01 MB (0.0%) |
| Loader peak, later start | 257.4 MiB | 257.4 MiB | 0 |

Reading (Judgement): v3 changed what happens when files are missing or stale, not the speed. The one timed change, skipping the zip checks on a later start, saved 4 ms, which no `full_run` can show. In the table above everything else moved by 0-9% in both directions on unchanged code, except the migraine query with the index (+92%, 1.68 → 3.22 ms, a few ms, Q14). Over every cell of the two `summary.csv` files the short values moved more: at 100% the GIN build +19% (1.31 → 1.56 s), `build_drugs` +27% (0.21 → 0.27 s) and the other three conditions with the index +30% to +69% (2-9 ms); at 25% and 50%, for example, the db peak at 25% −19% and on the fly at 50% +22% (arithmetic). That is this machine's run-to-run noise between two series about 2.5 hours apart, so a claim that rests on a difference smaller than about 10% between two benchmarks here is not supported, and on a step under 2 s or a query of a few ms not even a larger one. Chart: `v2_vs_v3.png` (`measure/charts_v2_v3.py`); the per-version charts are `time_vs_size.png`, `query_modes.png`, `disk_db_vs_raw.png` and `memory_peak.png` in this folder.
