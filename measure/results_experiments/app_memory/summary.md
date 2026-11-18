# App memory while a browser uses the dashboard, 100%, one fresh stack (`measure/app_memory.py`)

**The question** (from our first round of checks): benchmark v1 read the app's memory while nobody used the page. Its query phase runs `bench_queries.py` in the loader image, so the app only answered `/_stcore/health` (`measure/predictions.md`, P32). What does the app use while it serves searches?

**What changed, one thing:** a visitor. The stack, the data (100%, from the extract) and the sampler are the benchmark's; here a real browser uses the page.

**Protocol** (`output.txt`, 17:46:23-17:48:10 UTC on 5 Nov 2026, compose project `de-exp`, port 8571; committed in `f0bcd60`):
- `docker compose down -v`, then `up -d`: db, the loader from the extract, then the app. The dashboard was ready after 22.3 s.
- `docker stats --no-stream`, a new call every 0.5 s (`MemorySampler` of `measure/benchmark.py`, as it was in v2), in three phases:
  - **idle:** 20 s after the dashboard answered `/_stcore/health`, no browser connected;
  - **browser:** while `measure/app_memory.js` drives Chromium through Playwright: 8 conditions (migraine, cancer, epilepsy, hypertension, asthma, acne, type 2 diabetes, pain), each searched and then drilled down into its top ingredient, twice: 16 searches and 16 drill-downs (`events.csv`). 41.056 s by the script's clock, 41.5 s wall, 0 exceptions and 0 page errors;
  - **after:** 20 s after the browser closed.
- Raw samples: `docker_stats_samples.csv`. Summary per service and phase: `peaks.csv`.

**Results** (`peaks.csv`, MiB):

| Service | Phase | Samples | Median | Max | Max CPU |
|---|---|---:|---:|---:|---:|
| app | idle | 40 | 46.5 | 52.4 | 25.5% |
| app | browser | 83 | 132.7 | 138.4 | 123.7% |
| app | after | 40 | 132.8 | 135.0 | 14.3% |
| db | idle | 40 | 168.1 | 208.2 | 93.7% |
| db | browser | 83 | 216.3 | 217.8 | 20.7% |
| db | after | 40 | 217.3 | 218.8 | 8.2% |

**One caveat on the samples:** this ran with v2's sampler, which wrote a reading twice when two overlapping calls returned it (fixed in benchmark v3, `docs/decision_log.md` D-51). The file holds 326 rows, of which 167 are distinct (arithmetic on `docker_stats_samples.csv`), so the "Samples" column counts some readings twice and the real resolution is about 1 s. The maxima do not change: on the distinct rows they are the same 52.4 / 138.4 / 135.0 MiB for the app and 208.2 / 217.8 / 218.8 MiB for db.

**What it means:**
- The app's heaviest step is serving searches: it peaked at 138.4 MiB, about 3 times its idle median of 46.5 MiB (arithmetic). The benchmark's app peak, with no visitor, was 52.8 MiB at 100% in v2 (`measure/results_v2/summary.csv`, `peak_mem_app_full_run`), so the benchmark alone under-reports the app.
- The app stays near its peak after the browser closed (median 132.8 MiB). Judgement, not checked: Streamlit keeps the session and its cached data after the visit.
- db: 216.3 MiB median while serving, against 168.1 MiB idle. Its idle maximum, 208.2 MiB at 93.7% CPU with no browser connected, is one spike we cannot explain from these files.
- Decision: no code change; the README reports the browser peak (`docs/decision_log.md` D-36).

**The course on this:** : "MEMORY: How much RAM each container uses. Look at the highest value, while the heaviest step runs. (docker stats)". For the app, the heaviest step is a user searching, which the benchmark does not do.
