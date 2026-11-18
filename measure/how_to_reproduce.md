# How to reproduce the measurements

The protocol is 's: **3 sizes (25%, 50%, 100% of the usable labels) × 3 runs, report the mean, write down the laptop, change one thing at a time.** `measure/benchmark.py` runs all of it; `measure/charts.py` draws the charts. It is the template's protocol v2 (sizes interleaved and rotated each round, a fresh database volume and, on Linux, an empty OS file cache before every run, the load average recorded, the with/without-index order alternated between runs; every run reported).

The sizes are hash buckets of `set_id` (`docs/decision_log.md` D-2): 25% = 19,546 labels, 50% = 39,042, 100% = 78,472. **In v1, and on every v2 and v3 first start, the loader reads all 14 zip files** (the bucket of a label is known only after reading it), so the step `parse` costs about the same at 25% and at 100% (D-3). v2 and v3 later starts read the extract `data/clean` instead of the zips (D-29, D-38); a v3 later start does not even open the zips (D-44). That is a finding, not a fault of the benchmark: it is the part of the pipeline that less data does not make shorter (Amdahl's serial part). The raw input (`raw_zip`, `raw_json`) is therefore the same at every size; what grows is `kept_indications_text`, the text that reaches the database.

## Before you start (Mac with Docker Desktop)

- Close other heavy programs: the numbers depend on what else the laptop is doing. `benchmark.py` records the 1-minute load average twice per run, before `down -v` and after a 30 s settle (`machine_load_1min_before_down` / `machine_load_1min_after_settle`; v1 kept one value, `machine_load_1min`).
- Docker Desktop → Settings → Resources: note the CPUs and memory given to Docker. `benchmark.py` writes them down too ("GiB for containers" in `machine.txt`), because on a Mac containers run inside Docker Desktop's VM, not directly on macOS.
- Apple Silicon: `postgres:16` and `python:3.12-slim` are multi-arch images that include arm64 (`docs/evidence/arm64_check.txt`: the template's check, copied with a note; it applies here because the base tags and the app's four pins are the same), and the loader's two libraries have arm64 wheels for Python 3.12 on PyPI: `ijson-3.6.0-cp312-cp312-manylinux2014_aarch64...whl` and `psycopg_binary-3.3.6-cp312-cp312-manylinux_2_27_aarch64...whl` (checked 5 Nov 2026 with `pip download --only-binary=:all: --platform manylinux_2_28_aarch64 --python-version 3.12 ijson==3.6.0 psycopg-binary==3.3.6`, from the cloud VM, not on a Mac). Nothing changes in the commands. Check that the loader log says `ijson_backend=yajl2_c`: the pure-Python backend would make `parse` several times slower (Judgement, not measured).
- The 14 files (1.86 GB) must be in `data/raw/` already: run `docker compose up --build` once and let the loader download them. The same first start writes the extract `data/clean/labels_<export_date>_<clean_version>.csv` that benchmarks v2 and v3 need (D-29, D-43). Keep `data/raw` for the benchmark even though a v3 later start does not need it (D-44): `benchmark.py` reads the zip sizes from `data/raw`, and the first starts parse the zips. The benchmark times the pipeline, not the download (`download` is still recorded: about 0 s when the files are cached).
- `benchmark.py` uses only Python's standard library: the `python3` that comes with macOS (or Homebrew) is enough. `charts.py` needs matplotlib and pandas, installed in a venv (below). Python 3.11 or newer.
- Disk: each run starts from an empty volume. The database (`pg_database_size`, step `disk_database`) is 41.3 / 73.7 / 138.2 MB at 25 / 50 / 100% in v1 (`measure/results/summary.csv`) and 41.3 / 73.8 / 138.3 MB in v2 (`measure/results_v2/summary.csv`). Add the 1.86 GB of zips and, from v2, the 74.4 MB extract (`extract_csv`). An extract written by other cleaning rules stays next to it until you delete it (the loader names it in its log, D-43).

## 1. Build and run the benchmark

From the repository root:

```bash
cp .env.example .env                                  # once
docker compose up --build                             # once, to download data/raw; then Ctrl-C
docker compose down -v
python3 measure/benchmark.py --drop-caches            # 3 sizes x 3 runs = 9 full runs
```

On a Mac `--drop-caches` is skipped with a note in every run (`os_cache_dropped = 0`): it needs Linux and root. The runs are still interleaved, so cache state does not line up with size.

**Benchmark v2** (after the fixes of our first round of checks; results in `measure/results_v2/`, v1 in `measure/results/` is kept as the "before"):

```bash
python3 measure/benchmark.py --drop-caches --first-start 3 --out measure/results_v2
```

- `data/clean` (the extract, commit 565a0a9) is **kept between runs, like `data/raw`**: the 3 × 3 series (mode `generated`) measures the normal start, which reads the extract (`read_extract`) instead of parsing the zips. It needs the extract once: run `docker compose up` before (the benchmark stops with a message if it is missing).
- `--first-start N`: after the 3 × 3 series, N runs at 100% (mode `first_start`) that **delete `data/clean` first**, so the loader parses the 14 zips and writes the extract again (`parse` + `write_extract`). No query benchmark in them (same rows, same queries); `disk_database` is recorded instead. Each run checks that the loader took the path of its mode, else the benchmark stops.
- The load average is read twice: **before `down -v`** (`machine_load_1min_before_down`: the tail of the previous run) and **after `down -v`, the cache drop and a 30 s settle**, just before `up` (`machine_load_1min_after_settle`). v1 read it once, right after `down -v` and the cache drop (`machine_load_1min`), so it included their own work. The 1-minute load average decays with a 1-minute time constant: 30 s lowers what `down -v` and `sync` add, it does not remove it.
- The `--extra-tsv-after` runs are gone: the tsv during/after COPY was measured in v1 (D-9). To re-run v1 exactly: `git show d3c7887:measure/benchmark.py > /tmp/benchmark_v1.py` and run it with `EXTRACT_CACHE=0` in the shell, because the v2 loader reads the extract by default.

**Benchmark v3** (after our second round of checks; results in `measure/results_v3/`; v1 and v2 stay unchanged as the "before"):

```bash
git show dcbefbf --stat                               # the predictions were committed before the runs
python3 measure/benchmark.py --drop-caches --first-start 3 --out measure/results_v3
```

- **The same protocol as v2**, on purpose (D-52): only the code changed between v2 and v3, so the comparison changes one thing. The timed pipeline is the v2 pipeline; what changed is the `download` step of a later start, which now returns before the zip checks when the extract of this export and of these cleaning rules exists (D-44), and the extract's name, which carries `clean_version` (D-43). `benchmark.py` finds the extract as `data/clean/labels_<export_date>_*.csv`.
- **Predictions first:** `measure/predictions_v3.md` (`dcbefbf`, 20:27:31 UTC) holds 28 predicted values with ranges, each marked **v2**, **v3ev** (the `docs/evidence/v3_*.txt` runs) or **new**. The verdicts after the runs are in `measure/results_v3/verdicts.md`, with the rule of `measure/README.md` (|gap| ≤ 10% confirmed, ≤ 25% close, else missed).
- **`docker stats`:** a reading returned by two overlapping calls is written once (`d794808`, D-51), so `docker_stats_samples.csv` has no duplicate rows; the peaks are computed as before.
- **Chart, v2 against v3** (in the venv of section 2): `python measure/charts_v2_v3.py` writes `measure/results_v3/v2_vs_v3.png` from the two `summary.csv`.

All rows are **appended** to `raw_runs.csv` in the `--out` folder, and `summary.csv` is recomputed from all of them. To reproduce, give a new folder (for example `--out measure/results_mine`): `measure/results/` (v1), `measure/results_v2/` (v2) and `measure/results_v3/` (v3) are the committed results, and appending to them would mix runs.

All options:

| Option | Default | Meaning |
|---|---|---|
| `--sizes` | `0.25,0.5,1.0` | `SAMPLE_FRACTION` values = hash buckets {0}, {0,1}, {0,1,2,3}; `none` = only the first starts |
| `--runs` | `3` | runs per size |
| `--project` | `drug-explorer` | docker compose project name (`-p`) |
| `--app-port` | `8501` | dashboard port on the laptop (`APP_PORT`) |
| `--first-start` | `0` | after the sizes × runs, N runs at 100% that delete `data/clean` first (parse + write the extract); no query benchmark in them |
| `--out` | `measure/results` | output folder (relative to the repo root, or absolute) |
| `--timeout` | `3600` | seconds allowed for one `docker compose up` / query benchmark |
| `--order` | `interleaved` | `interleaved` = round r runs the sizes rotated by r-1 (25-50-100, 50-100-25, 100-25-50); `blocks` = all runs of one size, then the next |
| `--drop-caches` | off | empty the OS file cache before every run (`sync; echo 3 > /proc/sys/vm/drop_caches`; Linux and root only) |

Ctrl-C is safe: the stack is stopped (`docker compose down`, the volume stays) and the rows of finished runs are kept.

**How long it takes** on the test machine (a 4-vCPU Linux VM, 5 Nov 2026), from the last line of each `benchmark_log.txt`: v1 took 1275 s for 12 runs (9, plus 3 `--extra-tsv-after` runs), and v2 took 1019 s for 12 runs (9 later starts, plus 3 first starts). v3 has the same 12 runs as v2: 1071 s. One run is its `full_run`, then the query benchmark, `down -v` and, in v2, a 30 s settle. From `summary.csv`:
  - `full_run`: v1 74.34 / 81.68 / 89.74 s; v2 later start 11.71 / 14.82 / 21.32 s; v2 first start 81.48 s. v3 later start 11.93 / 16.30 / 22.37 s; v3 first start 87.44 s.
  - Migraine on the fly, the slowest query (`query_drugs_for_condition_on_the_fly_migraine`): 1.18 / 1.91 / 3.57 s in v1, 1.16 / 1.46 / 3.00 s in v2.

One test run at 25% happened before the predictions were written; it is disclosed in D-26, and its numbers are not results.

## What one (size, run) does

1. `docker compose down -v`: removes the containers **and the database volume**, so every run starts from an empty database (equal conditions). The zip files in `data/raw` stay, so the download is not repeated. With `--drop-caches`, `sync; echo 3 > /proc/sys/vm/drop_caches`: the 1.86 GB of zips (v2: also the extract) are read from disk again, not from memory. v1 then recorded `os.getloadavg()`. v2 records it before `down -v` and again after a 30 s settle (above).
2. Starts `docker stats --no-stream` in the background, a new call every 0.5 s, and keeps every sample and the peak per container (calls that finish together return the same reading; from v3 it is written once, so distinct readings are about 1 s apart; v2's `docker_stats_samples.csv` holds 2,791 rows, 1,413 unique), in two phases: `full_run` (the load) and `queries` (the query benchmark).
3. `docker compose up -d` with `SAMPLE_FRACTION`, `RUN_ID`, `TSV_MODE`, `APP_PORT`; waits until the loader exited with code 0 and `http://localhost:<port>/_stcore/health` answers 200. That time is `full_run`.
4. Reads the loader's own step timings (`time.perf_counter()`) from the table `pipeline_timings`.
5. Runs `loader/bench_queries.py` in the loader image (`docker compose run --rm --no-deps loader python bench_queries.py`; why there: D-40), with `BENCH_ORDER` = `with_first` in odd runs, `without_first` in even runs:
   - `drugs_for_condition` for 5 fixed conditions (migraine, hypertension, epilepsy, asthma, cancer), 1 untimed warm-up and 3 timed executions **with** the GIN index; the headline counts (`condition_summary`) and the drill-down `labels_for_drug` (migraine, its top ingredient) the same way;
   - `DROP INDEX labels_tsv_gin`, and the same **without** it (the planner must read the stored `tsv` of every label);
   - **on the fly**: `drugs_for_condition_on_the_fly` (`to_tsvector('english', indications)` in the query, no stored column, no index can serve it), 1 warm-up and **only 1 timed run per condition**, because each takes seconds, not milliseconds;
   - the index is built again (timed: `index_build_bench`);
   - checks that the answer is the same in the three modes (`check_same_answer_<condition>` = 1), then the disk sizes and row counts.
   - `EXPLAIN (ANALYZE, BUFFERS)` of migraine in each mode is saved for run 1 of each size.
   - Automatic prepared statements are off (`prepare_threshold = None`): each timed execution is planned like one dashboard call (D-41).
6. Adds the kept indications text (`sum(octet_length(indications))`), the zip and JSON sizes, the memory peaks, and appends everything to `raw_runs.csv`.

**Caches:** the queries run on a **warm** cache (the warm-up fills it), in all three modes. The load runs on a cold OS cache only with `--drop-caches` (Linux).

## 2. Make the charts (in a venv, never inside the repo's folders that get committed)

```bash
python3 -m venv ~/venvs/de-charts
source ~/venvs/de-charts/bin/activate
pip install -r measure/requirements.txt
python measure/charts.py                 # reads measure/results/summary.csv, writes the PNGs next to it
python measure/charts.py --results measure/results_v2   # the same charts for v2
python measure/charts_v1_v2.py           # v1 against v2: writes measure/results_v2/v1_vs_v2.png
deactivate
```

## Output files (in `measure/results/` for v1, with the same names in `measure/results_v2/` for v2 and `measure/results_v3/` for v3)

| File | What it is |
|---|---|
| `raw_runs.csv` | Every measurement of every run. Columns: `size` (25%/50%/100%), `run`, `step`, `value`, `unit` (s, ms, MiB, MB, bytes, rows, count, bool, load), `environment` (OS, CPU, cores, RAM, Docker version and resources, `mode=generated|after`), `detail`. |
| `summary.csv` | One row per (size, mode, step, unit): `n`, `mean`, `min`, `max`, `std`, `median`. **std is the sample standard deviation (n−1).** For the queries, `n` = runs × 3 repetitions (the `_repN` suffix is dropped); on the fly, `n` = runs × 1. That pooled std mixes the spread inside a run with the spread between runs, so (v2) the queries also have `runs`, `run_mean_mean` and `run_mean_std`: the mean of each run's repetitions first, then the mean and std of those per-run means. |
| `docker_stats_samples.csv` | Every `docker stats` sample: size, run, mode, phase (`full_run` or `queries`), seconds since the start of the run, container, service, memory (MiB), CPU %. |
| `machine.txt` | The machine, Docker version and resources, image sizes and ids, PostgreSQL version, the loader's Python, ijson (and its backend) and psycopg versions, the raw input size. |
| `explain/<size>pct_<query>_<mode>.txt` | `EXPLAIN (ANALYZE, BUFFERS)` of `drugs_for_condition` (migraine) `with_index`, `without_index`, `on_the_fly`, and of `labels_for_drug` `with_index`, `without_index`; run 1 of each size. |
| `time_vs_size.png` | `parse`, `pipeline_total`, `full_run` (left) and `copy`, `index_build`, `analyze` (right) vs labels loaded, each with a dashed line for perfectly linear growth from the 25% point. |
| `query_modes.png` | `drugs_for_condition` with index, without index and on the fly: the mean over the 5 conditions per size, each condition at the largest size, and the drill-down; log scale. |
| `disk_db_vs_raw.png` | Zips, JSON, kept text, database, `labels` heap, TOAST, GIN index per size; log scale. |
| `memory_peak.png` | Peak memory per container per size, load and query phases apart. |
| `v1_vs_v2.png` | `measure/results_v2/` only: v1 against v2 (later start and first start) for the full run, getting the rows, the loader's peak memory and the main query. |
| `v2_vs_v3.png` | `measure/results_v3/` only: v2 against v3, the same four panels (`measure/charts_v2_v3.py`). |
| `verdicts.md` | `measure/results_v3/` only: each prediction of `measure/predictions_v3.md` against the v3 mean, with its gap and verdict. |

## Step names in `raw_runs.csv`

- Loader (seconds): `download` (about 0 s: files cached), `parse` (read and clean all 14 zips), `schema_and_truncate`, `copy` (COPY, with `tsv` computed by PostgreSQL in mode `generated`), `tsv_fill` (mode `after` only), `commit`, `index_build`, `build_drugs`, `analyze`, `pipeline_total` (everything after the download), `total_with_download`; `rows_loaded` (rows).
- Benchmark: `full_run` (s); `query_drugs_for_condition_<with_index|without_index|on_the_fly>_<condition>_rep<n>` (ms); `query_labels_for_drug_<with_index|without_index>_rep<n>` (ms); `pick_drill_drug` (the ingredient used by the drill-down, in `detail`); `bench_order`; `index_build_bench` (s); `os_cache_dropped`, `machine_load_1min` (v1), `machine_load_1min_before_down` and `machine_load_1min_after_settle` (v2, v3); `extract_deleted` (first starts), `read_extract`, `write_extract` (s), `extract_csv` (bytes, MB; v3: the newest `labels_*.csv` in `data/clean`).
- Answer checks: `count_labels_<condition>_<mode>`, `count_ingredients_<condition>_<mode>` (from `condition_summary`); `check_same_answer_<condition>` (1 = the same 25 rows in the three modes and the same counts with and without the index); `count_rows_labels`, `count_rows_drugs`.
- Disk (bytes and MB): `disk_database` (`pg_database_size`), `disk_labels_table` (`pg_relation_size('labels')`: the main heap file only), `disk_labels_gin_index` (`pg_relation_size('labels_tsv_gin')`), `disk_labels_indexes` (GIN + primary key), `disk_labels_total` (`pg_total_relation_size`), `disk_labels_toast` (= total − heap − indexes: the TOAST table and its index, where PostgreSQL moves long values compressed, plus the heap's free-space and visibility maps), `disk_labels_toast_only` (`pg_total_relation_size` of the TOAST table itself, to check the line before), `disk_drugs_total`, `disk_indications_column` and `disk_tsv_column` (`sum(pg_column_size(...))`: the two big columns as stored); `kept_indications_text` (uncompressed text); `raw_zip`, `raw_json` (the same at every size). In `pipeline_timings` itself, disk steps keep the bytes in the `rows` column and `seconds = 0`.
- Memory (MiB): `peak_mem_<service>_full_run` (during `docker compose up`: the load) and `peak_mem_<service>_queries` (during `bench_queries.py`; the `loader` service there is the benchmark client).

## Watching memory by hand

In a second terminal, while `docker compose up` runs:

```bash
docker stats                             # live table; look at MEM USAGE of each container while the loader runs
docker stats --no-stream                 # one snapshot
```

"Look at the highest value, while the heaviest step runs." Here the heaviest step for the loader is `parse` (it holds the kept rows in memory, D-4); for the database it is `copy` (stemming every label) and the index build.

## Checking a number

Every measurement in the README comes from a `summary.csv` (v1 `measure/results/`, v2 `measure/results_v2/`, v3 `measure/results_v3/`), which comes from its `raw_runs.csv`, or from the experiment files in `measure/results_experiments/` (section 3), or from the v3 evidence runs in `docs/evidence/v3_*.txt` (section 4). The timings of the last run are also in the database:

```bash
docker compose up -d db
docker compose exec db sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT run_id, step, round(seconds::numeric, 3) AS s, rows FROM pipeline_timings ORDER BY started_at"'
```

## 3. The v2 experiments: one change each

These scripts ran after our first round of checks (D-28, D-35, D-36, D-37), with the outputs in `measure/results_experiments/`. Each folder has a `summary.md`: what changed, the protocol, the numbers and what they mean. The first three use their own compose projects (`de-exp`; `app_memory.py` uses port 8571) and `down -v` their own volume; run them alone on the machine, as the benchmark ran. Each expects the extract in `data/clean/` (without it, the first load parses the zips and writes it). The commands below overwrite the committed output files, so write to another file to compare.

```bash
bash measure/gin_expression.sh > measure/results_experiments/gin_expression/runs.txt          # stored tsv vs GIN expression index, 25% and 100%, A B B A A B
python3 measure/gin_expression_summary.py > measure/results_experiments/gin_expression/summary_table.txt
bash measure/parallel_scan.sh > measure/results_experiments/parallel_scan/run.txt             # 100%: planner inputs, plans, timings
python3 measure/parallel_scan_summary.py > measure/results_experiments/parallel_scan/stats.txt
python3 measure/app_memory.py                                                                 # needs node with playwright (Chromium) on the host
python3 measure/round_effect.py > measure/results_experiments/round_effect/output.txt         # reads only the v1 results, starts no container
```

`gin_expression.sh` uses the loader mode `TSV_MODE=expression`, a measurement mode only: the app is never started in it.

## 4. The v3 evidence runs (second round of checks)

These are not benchmark runs: each tests one behaviour of the v3 loader, before (`main` at `b5ecc7c`, image `de-v3-loader:before`) and after, on the compose project `de-v3` (`APP_PORT=8581`). Each output file starts with the exact commands. The ones that need a broken or missing file work on **copies** of the zips in a temporary folder, never on `data/raw` (whose zips are hard links to the research download, D-7); `data/raw` is mounted read-only where it is used.

| File | What it shows | Decision |
|---|---|---|
| `docs/evidence/v3_extract_key.txt` | a changed cleaning rule: `main` reads the stale extract, v3 parses again | D-43 |
| `docs/evidence/v3_extract_without_zips.txt` | a later start with only the extract on disk; no manifest | D-44 |
| `docs/evidence/v3_missing_zip.txt` | a `.part` and a new export: `main` loops, v3 stops with "new export" | D-45 |
| `docs/evidence/v3_http_4xx.txt` | HTTP 403: 6 attempts in `main`, 1 in v3 | D-46 |
| `docs/evidence/v3_retry.txt`, `v3_app_waits_for_loader.txt` | retries with backoff logged; the app never started after exit 1 | D-47 |
| `docs/evidence/v3_reload_lock.txt` | how long a read waits while the loader reloads at 100% | D-49 |
| `docs/evidence/v3_startup_breakdown.txt` | where the fixed ~7 s of a later start goes | D-50 |

The two measurement scripts use the compose project `de-v3` and need the extract in `data/clean`. Run them from the repository root:

```bash
python3 docs/evidence/v3_startup_breakdown.py 3      # as root (cache drop): 3 later starts at 100%, each down -v, cache drop, 30 s settle, up -d;
                                                     # docker events, the loader's step log, HTTP polled every 0.05 s
python3 docs/evidence/v3_reload_lock.py              # with the de-v3 stack up at 100%: one reload while a probe in the app container queries every 0.5 s
```
