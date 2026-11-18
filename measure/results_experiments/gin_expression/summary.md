# GIN expression index against the stored `tsv` column, 25% and 100%, 3 loads each (`measure/gin_expression.sh`)

**What changed, one thing:** where the stemmed words live. A (`TSV_MODE=generated`, the v2 schema): the column `tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', indications)) STORED`, and the GIN index on `tsv`. B (`TSV_MODE=expression`): no stored column, and the GIN index on the expression `to_tsvector('english', indications)`. In B the queries of `sql/queries.sql` are rewritten so that `tsv @@` becomes that expression, exactly as written in the index, so the planner can use it (`measure/gin_expression_queries.py`). Everything else is the same: the rows (from the extract), the loader, the one transaction, the queries' answers.

**Protocol** (`runs.txt`, first and last line: 17:41:10-17:45:05 UTC on 5 Nov 2026, commit `ca5f98e`, compose project `de-exp`, the VM of `measure/results_v2/machine.txt`):
- At 25% and at 100%, 6 loads in the order A B B A A B, so each mode is first, middle and last once.
- Before every load, `docker compose down -v`: a fresh database volume. The load runs `docker compose run --rm --no-deps loader` with `EXTRACT_CACHE=1` (the rows come from `data/clean`, the zips are not parsed).
- After each load, `gin_expression_queries.py` reads the disk sizes, runs the migraine query and the phrase "type 2 diabetes" (1 untimed warm-up, then 3 timed repetitions each), and saves one `EXPLAIN (ANALYZE, BUFFERS)` of each into `explain/`.
- The load average before each load is in `runs.txt` (0.27 at the first load, 1.41 at the last).
- `summary_table.txt` is written by `measure/gin_expression_summary.py` from `runs.txt`: mean (min-max) of the 3 loads per mode; the query rows are 3 loads × 3 repetitions, n = 9.

**Results at 100%** (`summary_table.txt`, means; B / A is the file's own column):

| Step | A, stored column | B, expression index | B / A |
|---|---:|---:|---:|
| `copy` | 10.719 s | 1.421 s | 0.13 |
| `index_build` | 1.404 s | 10.835 s | 7.72 |
| `analyze` | 1.230 s | 4.550 s | 3.70 |
| `pipeline_total` | 14.957 s | 18.438 s | 1.23 |
| `disk_database_bytes` | 138,118,850 | 88,704,706 | 0.64 |
| … heap | 71,827,456 | 54,263,808 | 0.76 |
| … TOAST | 40,484,864 | 9,027,584 | 0.22 |
| … GIN index | 11,501,568 | 11,091,968 | 0.96 |
| … `tsv` column (sum of `pg_column_size`) | 46,488,189 | none | |
| migraine query (n = 9) | 1.861 ms | 1.904 ms | 1.02 |
| "type 2 diabetes" query (n = 9) | 10.432 ms | 470.409 ms | 45.09 |
| rows removed by the index recheck, "type 2 diabetes" | 143 | 143 | 1.00 |

**At 25%** the pattern is the same: `copy` 2.752 → 0.362 s, `index_build` 0.463 → 2.705 s, `analyze` 0.658 → 2.933 s, the database 41,303,063 → 28,974,103 bytes, migraine 2.452 → 1.577 ms, "type 2 diabetes" 4.256 → 125.831 ms (`summary_table.txt`, first table).

**Same answers:** 680 labels and 48 ingredients for migraine, 1,337 labels and 66 ingredients for "type 2 diabetes", in both modes and every load (100%); 160 / 19 and 343 / 45 at 25%.

**What the plans show** (`explain/100pct_*_type_2_diabetes.txt`): in both modes the Bitmap Index Scan on `labels_tsv_gin` returns 1,480 candidate rows, and the Bitmap Heap Scan removes 143 of them ("Rows Removed by Index Recheck: 143"), leaving 1,337. The Bitmap Heap Scan ends at 9.461 ms with the stored column and at 447.514 ms with the expression index. A GIN index on a `tsvector` keeps the words, not their order, so a phrase must be checked again on each candidate row (PostgreSQL documentation; the 143 removed rows show it). With the stored column that check reads the stored words; without it, PostgreSQL must stem each candidate's text again. Migraine is one word, so nothing is rechecked (0 rows removed in both modes), and its time does not change.

**What it means:** the expression index saves 49.4 MB of disk at 100% (138,118,850 − 88,704,706 bytes, arithmetic) and makes COPY 7.5 times faster, because COPY no longer stems every label. But the stemming moves into the index build and ANALYZE, so the whole pipeline is 3.5 s longer (18.438 − 14.957 s, arithmetic), and every condition of more than one word pays the recheck at every search: 470 ms instead of 10 ms. The user waits for the search, not for the load, so the stored column stays (`docs/decision_log.md` D-28). Why ANALYZE is slower is Judgement, not checked: probably because it also gathers statistics on the index expression, which stems the sampled rows again.

**The course on this trade-off**: "Note what an index really is: one more copy of your data, kept in the order that answers a particular question. It speeds up reads, slows down writes, and takes disk space — the same trade the cache made, decided by you this time." Here the stored column is a second copy of the words that the index answers from, and this experiment measures what that copy costs (46.5 MB, a slower COPY) and what it buys (the phrase query). "Change one thing at a time."
