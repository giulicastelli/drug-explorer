# Predictions for benchmark v3, written before the runs

"Predict, then verify." Review round 2: nothing was predicted before benchmark v2. This file is committed on `add-benchmark-v3` **before** `measure/benchmark.py` writes anything into `measure/results_v3/`; the commit time and the first line of `results_v3/benchmark_log.txt` show the order. Every number in the tables is a **prediction**; the reasons are Judgement unless they name a file. Verdicts after the runs: `measure/results_v3/verdicts.md`, with the README's rule (gap = (measured − predicted) / predicted; |gap| ≤ 10% confirmed, ≤ 25% close, else missed).

## What changed between v2 and v3 (the code the benchmark runs)

- `loader/load_fda.py` (merge `7032f94`): the extract is named `labels_<export_date>_<clean_version>.csv`; when it exists, `download()` returns before the 14 zips are looked at (no `size_ok`, no `check_zip`). A first start (no extract) still checks every zip, as in v2. The parse, the COPY, the index, `drugs`, ANALYZE and the one transaction are unchanged. A 4xx answer is no longer retried (no download happens in the benchmark).
- `measure/benchmark.py` (`d794808`): a `docker stats` reading returned by two overlapping calls is written once. The peaks do not change.
- Protocol: the same as v2, `python3 measure/benchmark.py --drop-caches --first-start 3 --out measure/results_v3` (`measure/how_to_reproduce.md`): 3 sizes × 3 runs, interleaved and rotated, then 3 first starts at 100% that delete `data/clean` first.

So the pipeline that is timed is the v2 pipeline. **The main prediction is "no change beyond run-to-run noise"**, except the `download` step of a later start. A benchmark of unchanged code is a repeatability test: what it can show is how large the noise is, not that the code got faster.

## What was already known (and so proves little when it matches)

- **v2** (`measure/results_v2/summary.csv`, same machine, 17:57-18:14 UTC): every row below, at every size. Marked **v2**.
- **v3 code, before this file** (same machine, compose project `de-v3`): 3 later starts at 100% with the benchmark's protocol, 20:04-20:07 UTC (`docs/evidence/v3_startup_breakdown.txt`): `full_run` 23.62 / 22.14 / 23.76 s, `pipeline_total` 16.72 / 15.08 / 16.66 s, `copy` 12.53 / 10.82 / 11.89 s, `read_extract` 1.20 / 1.21 / 1.68 s, `index_build` 1.29 / 1.72 / 1.46 s, `build_drugs` 0.26 / 0.20 / 0.21 s, `analyze` 1.35 / 1.02 / 1.33 s, `download` 0.006-0.009 s, fixed part 6.90-7.10 s. Two more later starts at 100% without the zips: `pipeline_total` 15.85 and 14.43 s, `read_extract` 1.26 and 1.10 s (`docs/evidence/v3_extract_without_zips.txt`). The v3 extract is byte-identical to v2's, 74,388,073 bytes; kept rows 19,546 at 25% and 78,472 at 100% (`docs/evidence/v3_extract_key.txt`). Marked **v3ev**.
- **new**: no v3-code value existed when this file was written: every later-start row at 25% and 50%, all first-start rows (v3 code, 100%), the peaks, the queries, the database size and the sample count.

How the predictions were made (Judgement): at 25% and 50%, the v2 mean, raised a little for COPY because the v3ev COPY at 100% was 11% slower than v2's (11.75 vs 10.62 s, arithmetic) on the same code; at 100%, between the v2 mean and the v3ev mean, because both are this machine and this code path. The range is the interval I would not be surprised by: about the v2 and v3ev min-max, widened by the spread of the noisiest series.

## Time (s, mean of 3 runs; later start = mode `generated`, reads the extract)

| # | Step | 25% | 50% | 100% | Known before | Reason |
|---|---|---:|---:|---:|---|---|
| Q1 | `download` (later start: manifest reused, zips not checked) | 0.007 (0.004-0.012) | 0.007 (0.004-0.012) | 0.007 (0.004-0.012) | v2 (0.0127 / 0.0107 / 0.0116, with the zip checks); v3ev 100% | The only step whose code changed. v2's 0.011 s already included `check_zip` on 14 central directories, so the saving is about 5 ms: invisible in `full_run`. |
| Q2 | `read_extract` | 1.0 (0.85-1.25) | 1.1 (0.95-1.35) | 1.3 (1.1-1.7) | v2; v3ev 100% | The whole 74.4 MB extract is read and parsed at every size (the bucket filter comes after), so nearly flat; it grows only with the rows appended to the list. |
| Q3 | `copy` | 3.0 (2.5-3.7) | 5.5 (5.0-6.2) | 11.2 (10.4-12.6) | v2; v3ev 100% | Linear in the text, PostgreSQL's `to_tsvector` per row (D-9). v2's 25% run 1 was the outlier (3.56 s vs 2.52 / 2.74 s, `results_v2/raw_runs.csv`); one such run raises a mean by about 0.3 s. |
| Q4 | `index_build` | 0.31 (0.26-0.40) | 0.67 (0.55-0.80) | 1.40 (1.25-1.75) | v2; v3ev 100% | One pass over the stored `tsv`, about linear. |
| Q5 | `build_drugs` | 0.05 (0.04-0.07) | 0.12 (0.08-0.17) | 0.22 (0.18-0.27) | v2; v3ev 100% | A GROUP BY on small columns. |
| Q6 | `analyze` | 0.52 (0.45-0.65) | 0.94 (0.85-1.10) | 1.05 (0.90-1.40) | v2; v3ev 100% | A 30,000-row sample from 50% on, so 50% ≈ 100%. |
| Q7 | `pipeline_total` (after the download) | 5.0 (4.4-5.8) | 8.4 (7.6-9.3) | 15.2 (14.2-16.9) | v2; v3ev 100% | Q2 + Q3 + Q4 + Q5 + Q6 + schema and commit (0.03 s). COPY is 60-75% of it. |
| Q8 | `full_run` (`up -d` to `/_stcore/health` = 200) | 11.9 (11.0-12.8) | 15.3 (14.1-16.3) | 22.1 (20.8-24.0) | v2; v3ev 100% | Q7 plus a fixed part of 6.9 s (v2 6.65-6.88 s, README; v3ev 6.90-7.10 s, 44% of it the db healthcheck). |
| Q9 | First start: `download` (all 14 zips checked) | | | 0.013 (0.009-0.020) | v2 (0.0127) | No extract on disk, so the v2 path. |
| Q10 | First start: `parse` (14 zips, 8.75 GB of JSON) | | | 59.1 (57.5-62.0) | v2 (58.74-59.73) | Same code. `CLEAN_VERSION` is one md5 at import (ms). Compute-bound in one Python process. |
| Q11 | First start: `write_extract` | | | 1.45 (1.3-1.7) | v2 (1.3953-1.5026) | Same 74.4 MB file. |
| Q12 | First start: `pipeline_total` | | | 74.7 (72.5-77.5) | v2 (73.22-76.30) | Q10 + Q11 + COPY 11.4 + index 1.45 + drugs 0.24 + analyze 0.95. |
| Q13 | First start: `full_run` | | | 81.6 (79.0-84.5) | v2 (80.32-83.15) | Q12 + the 6.9 s fixed part. |

## Queries (ms, warm; with/without index: mean of 3 runs × 3 repetitions; on the fly: 3 runs × 1)

| # | Query | 25% | 50% | 100% | Known before | Reason |
|---|---|---:|---:|---:|---|---|
| Q14 | Migraine, with the GIN index | 1.8 (1.2-2.8) | 1.8 (1.2-2.8) | 1.8 (1.2-2.8) | v2 (1.95 / 1.70 / 1.68) | Same rows, same index. Follows the 160 / ~340 / 680 matching labels, not the table; most of it is the round trip. |
| Q15 | Migraine, without the index (scan of the stored `tsv`) | 21 (18-26) | 50 (38-64) | 84 (72-105) | v2 (20.7 / 51.2 / 83.6) | A sequential scan of `labels`, linear in rows; v2's 50% values ranged 39-63 ms. |
| Q16 | Migraine, on the fly (`to_tsvector` per row) | 1,150 (1,050-1,300) | 1,480 (1,350-1,650) | 3,000 (2,800-3,300) | v2 (1,156 / 1,464 / 2,998) | Stems every label again, with 1 / 2 / 2 parallel workers (v2 plans). |

## Disk and rows

| # | Value | 25% | 50% | 100% | Known before | Reason |
|---|---|---:|---:|---:|---|---|
| Q17 | `rows_loaded` | 19,546 | 39,042 | 78,472 | v2; v3ev 25% and 100% | Same extract, same buckets. |
| Q18 | `disk_database` (MB), later start | 41.30 (±0.05) | 73.78 (±0.05) | 138.31 (±0.05) | v2 (41.3031 / 73.7789 / 138.3073) | Same rows, same PostgreSQL 16.15 image. Recorded after the query benchmark (index dropped and rebuilt). |
| Q19 | `disk_database` (MB), first start | | | 138.12 (±0.05) | v2 (138.1161) | No query benchmark in a first start, so slightly smaller than Q18. |
| Q20 | `extract_csv` (bytes) | 74,388,073 | 74,388,073 | 74,388,073 | v2; v3ev | Byte-identical extract. |

## Memory (peak of `docker stats`, MiB)

| # | Container, phase | 25% | 50% | 100% | Known before | Reason |
|---|---|---:|---:|---:|---|---|
| Q21 | loader, full run | 84 (79-88) | 140 (133-147) | 257 (245-270) | v2 (83.5 / 140.1 / 257.4) | The kept rows are held in a list until COPY: linear in rows. |
| Q22 | db, full run | 122 (115-130) | 169 (160-178) | 235 (222-248) | v2 (122.4 / 169.0 / 234.5) | `shared_buffers` plus the page cache of the files it writes. |
| Q23 | db, queries | 102 (90-117) | 189 (165-215) | 269 (235-300) | v2 (101.8 / 189.1 / 269.2) | The scans fill the buffer pool; v2's 100% values ranged 246-281. |
| Q24 | app, full run | 52.8 (50-56) | 52.8 (50-56) | 52.8 (50-56) | v2 (52.9 / 52.8 / 52.8) | Flat: the benchmark only calls `/_stcore/health`. |
| Q25 | First start: loader / db / app, full run | | | 259 / 237 / 52.7 (±5%) | v2 (258.9 / 237.4 / 52.7) | Same parse and load. |

## New in v3 only

| # | Value | Prediction | Known before | Reason |
|---|---|---|---|---|
| Q26 | `docker_stats_samples.csv`: rows with the same (size, run, mode, phase, t_s, container, mem, cpu) | 0 | new | `d794808` writes a reading once per pass. |
| Q27 | `docker_stats_samples.csv`: rows in all | 1,400 (1,150-1,700) | new | v2 had 1,413 unique of 2,791; the runs are as long as v2's. |
| Q28 | The first run of the 25% series has the longest `full_run` of that series (review round 2, finding (b), seen in v2) | yes, low confidence | v2 (yes: 12.33 vs 11.63 / 11.15 s) | Judgement: in v2 the first run came right after `compose build`; in v3 too, so the same warm-up effect is expected. A coin toss if it was chance. |

## What would surprise us (and what we would check)

- A later start at 100% more than 10% faster than v2's 21.32 s: the zip check cannot account for it (Q1), so it would be the machine; check the load average columns and COPY.
- `parse` more than 5% away from 59.1 s on the same code: check `machine_load_1min_after_settle` and the ijson backend line.
- Q26 above 0: the dedupe does not work, check the sampler.
