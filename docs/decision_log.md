# Decision log

Every unknown met during the build, the default chosen and why; every "YOUR CHOICE" item of the course instructions, with the alternatives considered.
Format: **D-n, topic** → decision, alternatives, reason. "Judgement" marks reasoning that is ours, not the course's; "prediction" marks a number we did not measure. Numbers marked [M] come from the files in `docs/evidence/` (core test, 5 Nov 2026, Docker on a 4-vCPU VM, one run each unless said otherwise; not a benchmark).

## Data and loading (Role A)

**D-1, ijson, an extra library.** → the loader reads each zip with `ijson.items(f, "results.item")`: one label at a time, straight from the compressed file. Alternative: `json.load` (standard library). Reason, (memory): one partition is 602-712 MB of JSON (8,749,654,318 bytes for the 14, read by the loader from the zip headers [M]); `json.load` must hold the whole text and every Python object built from it at once. Judgement, prediction: several GB for one partition, on a laptop with 8 GB. Measured with ijson: the loader's peak memory (`getrusage`, peak RSS of the process) was 74-77 MiB at 25% and 178 MiB at 100% [M] (`docs/evidence/core_loader_100pct.log`), and most of it is the kept rows (D-4), not the parser. ijson 3.6.0 (12 Oct 2026 on PyPI) uses its C backend (`ijson_backend=yajl2_c` in the log). Nothing is unzipped to disk.

**D-2, 25% / 50% / 100% = hash buckets of `set_id`.** → `bucket = int(md5(set_id)[:8], 16) % 4`; 25% = {0}, 50% = {0, 1}, 100% = {0, 1, 2, 3}. Alternatives: the first 4 / 7 / 14 zip files (rejected: the files are not samples of the same kind; the share of named labels (with an `openfda` block) per file goes from 19.1% to 39.8%, and 75.5% in file 14, research counts in `docs/evidence/fp_sample.md` section 4); by year (rejected: 93% of the usable labels are from 2023-2026). Reason: nested, reproducible and uniform: 19,546 / 39,042 / 78,472 rows (research [M]; 19,546 and 78,472 again in the core test [M]; bucket counts 19,546 / 19,496 / 19,684 / 19,746).

**D-3, The parse does not shrink with the sample: it is timed as its own step.** → at every size the loader reads all 14 zips (the bucket of a label is known only after reading its `set_id`), so the step `parse` costs about the same at 25% and 100%: 58.1-66.8 s in the five runs at 25% whose tables are in `docs/evidence/` (66.8 s in the fresh-clone test, `docs/evidence/core_loader_25pct.log`; corrected after review: this entry first said "58.1-78.3 s in seven runs", which no file in the repository shows), 62.5 s at 100% [M]; the load proper (`copy`) is 2.8-3.5 s at 25% and 10.8 s at 100% [M]. This is Amdahl's serial part: at 25%, more than 90% of the pipeline is a part that 4× less data does not reduce. Alternatives: (a) save a cleaned extract of all buckets in `data/` on the first run and load the sizes from it (rejected for now: a second cache that can go stale against `download.json`, more code, and it would hide the real cost of a first start on a laptop); (b) choose the size by zip file (rejected, D-2). Judgement: the parse is CPU-bound in Python (each label becomes a dict with every section of the label, about 600 MB of JSON per file in about 4-7 s); making it cheaper, e.g. building only the fields we keep, is an open question for the team. After the review, alternative (a) was built: D-29.

**D-4, Kept rows are held in a list, then sent with one COPY.** → `parse()` returns the kept rows; `copy` sends them. Alternative: stream each row into COPY while parsing (flat memory). Reason: the two steps can then be timed apart (D-3), and the list is small: 74-77 MiB peak at 25%, 178 MiB at 100% [M]. The cost: the loader's memory grows with the sample, and the measurements should show it.

**D-5, COPY, in one transaction, after TRUNCATE.** → `schema.sql` (all `IF NOT EXISTS`), `DROP INDEX`, `TRUNCATE labels, drugs`, COPY, COMMIT. A second run on the same volume loaded the same 19,546 rows and 3,554 drugs, not twice as many [M] (run `idempotency-rerun-25`). A failure before COMMIT leaves the previous load in place. Alternative: `executemany` (one INSERT per row; not measured here: a comparison for Role E if wanted). After the review: everything up to `load_info` is now one transaction (D-30).

**D-6, Download: cached, reused with its own manifest, checked three ways.** → files in `data/raw/` are reused; `download.json` is reused with them, because the files and the manifest belong to one export (`export_date` 2026-11-05); to get a newer export, delete `data/raw/`. Retries with exponential backoff and jitter on `URLError`, timeouts, `ConnectionError` (includes `ConnectionResetError`), `http.client.HTTPException` (a body cut short) and `ssl.SSLError`, as in the template; `.part` file then rename. Checks: (1) the zip opens and holds one non-empty `.json`; (2) its size matches the manifest's `size_mb` (MiB, two decimals) within 0.01 MiB; (3) the number of labels parsed matches the manifest's `records` for that file. The download is timed apart (step `download`) and excluded from `pipeline_total`. Failure test: a zip cut to 10 MB → `[loader] FAILED: RuntimeError: drug-label-0014-of-0014.json.zip: not a readable zip (File is not a zip file). Delete it and run again.`, exit code 1 [M]. After the review this case re-downloads the file once and succeeds; exit 1 is now for a file still wrong after that, a broken zip of the right size, or a new export (D-32).

**D-7, On the cloud VM, `data/raw/` holds hard links to the research download.** → the 14 zips and `download.json` were downloaded once from `download.open.fda.gov` / `api.fda.gov` by the research step (1.86 GB, 85.7 s); `data/raw/` was filled with `cp -l` of those files, to avoid downloading 1.86 GB again. The loader's own download path was tested once into a temporary `DATA_DIR` holding files 1-13 only: it fetched `download.json` and `drug-label-0014-of-0014.json.zip` (23.21 MiB) in 1.12 s, both byte-identical (`cmp`) to the research copies, then loaded 19,546 rows [M] (run `download-test-p14`). On a laptop nothing is pre-filled: the loader downloads all 14 files.

**D-8, Which labels, which names.** → a label is kept when it has a non-empty "Indications and usage" and an ingredient name: `openfda.substance_name`, or `openfda.generic_name` when the substance is missing (1,476 labels). Dropped and counted in `pipeline_timings.detail` and `load_info`: no indications 11,921; no name 172,514 (69.1% of the export has no `openfda` block, research counts in `docs/evidence/fp_sample.md` section 4); 262,907 read [M], the same as the research count. `substance_key` = the sorted, upper-case, whitespace-normalised substance names joined with " + " (not the generic name, which has spelling variants). `product_type`: "HUMAN PRESCRIPTION DRUG" → Rx, "HUMAN OTC DRUG" → OTC, anything else in title case ("Cellular Therapy", 18 labels). One label has an `effective_time` that is not a date (stored NULL) and one is dated 2026-11-23, after the export [M]; both are kept.

## Database and queries

**D-9, The stored tsvector: generated during COPY, not added after.** → `tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', indications)) STORED`. Alternative: COPY without the column, then `ALTER TABLE ... ADD COLUMN tsv ... STORED` (one rewrite of the table), kept as `TSV_MODE=after` for this measurement. Measured at 25% on a fresh volume, one load at a time, order generated, after, generated, (two more generated loads), after [M]:

| mode | COPY | add tsv | commit | total | table (heap) |
|---|---:|---:|---:|---:|---:|
| generated | 2.99 / 3.52 / 2.85 / 2.79 s | — | 0.00-0.05 s | 2.79-3.52 s | 17,891,328 bytes |
| after | 0.34 / 0.35 s | 2.78 / 2.88 s | 0.04 / 0.05 s | 3.16 / 3.28 s | 17,825,792 bytes |

The two cost the same within the spread of the generated runs: the work is the same (stem every label once), done during COPY or in one pass after it. COPY alone is 8-10× faster without the column (0.34-0.35 s against 2.79-3.52 s): 87-90% of the load is `to_tsvector`, not moving rows (arithmetic on the rows above). We keep `generated`: one table definition, nothing dropped and added back, and a row can never exist without its words. Evidence: `docs/evidence/core_pipeline_timings_25pct.txt` (generated), `docs/evidence/core_tsv_after_25pct.txt` (second after run; the first after run and the first generated run are in the terminal log only, their volumes were deleted). Not 3 runs each with a protocol: the measurements part can repeat it if it goes into the README.

**D-10, One GIN index on `tsv`, built after COPY.** → `sql/indexes.sql`; the loader drops it before TRUNCATE and builds it after COMMIT, so COPY does not update it row by row. Build 0.30-0.46 s at 25%, 1.49 s at 100%; size 3.4 MB at 25%, 11.5 MB at 100% (11,501,568 bytes) [M]. `CREATE_INDEX=0` loads without it, for the comparison. Only one index: `set_id` has its primary key (3.3 MB at 100%) and `drugs.substance_key` too.

**D-11, The queries.** → `phraseto_tsquery('english', condition)`: the same stemming as the stored column ("migraines" finds "migraine"), and the words must be in order and next to each other ("type 2 diabetes"). `drugs_for_condition` groups the matching labels first and joins only the 25 groups with `drugs` (reduce first, join after). `labels_for_drug` limits to 20 rows before `ts_headline`, which re-reads the whole text of each row it is given. `drugs_for_condition_on_the_fly` computes `to_tsvector` on every row and cannot use the index: at 100%, 3,266 ms in EXPLAIN ANALYZE (3,962 ms timed from Python, one run) against 1.3 ms with the index, and the same 25 rows [M] (`docs/evidence/core_queries_100pct.txt`). What the queries do not do (open for the dashboard part): no synonyms ("high blood pressure" is not "hypertension"); a mention is not a treatment ("cancer": the top 3 at 100% are sunscreens, 1,093 + 1,090 + 563 OTC labels [M]; in 20 random research matches, 15 were false; a rule that removes most of them, and its cost, is in `docs/evidence/fp_sample.md` sections 1-2).

## Docker (Role D)

**D-12, Same Docker pattern as the template.** → ex4 compose (named volume, `pg_isready` healthcheck, `service_healthy`, `service_completed_successfully`), build context at the repo root so `sql/` goes into the images, `requirements.txt` before the code, non-root UID 1000, only `APP_PORT` published, `DB_HOST=db`. Pins: `psycopg[binary]==3.3.6` (18 Sep 2026 on PyPI) and `ijson==3.6.0` (12 Oct 2026) for the loader; the app keeps the template's `streamlit==1.66.0`, `altair==6.3.0`, `pandas==3.0.6`, `psycopg[binary]==3.3.6`. On the cloud VM `python:3.12-slim` is a variant that trusts the VM's TLS proxy (template `docs/environment.md`, D-4); the project files name the official image. After the review: lock files for the indirect libraries (D-33); the base tags stay (D-42).

## Design documents (5 Nov, before the benchmark)

Added with `docs/dataset_decision.md`, `docs/schema.md`, `docs/environment.md` and `measure/predictions.md`. Entries D-1 to D-12 above are unchanged.

### The project

**D-13, Question and dataset.** → "Which drugs treat this condition?", answered from the openFDA drug label bulk export (CC0). Alternatives: SIDER 4.1 indications (runner-up: the answer is already coded, 30,835 rows, from 2015), the EMA medicines table (runner-up: 2,754 rows, no named open licence), openFDA NDC and the AIFA registry (no indications text), DrugCentral, ChEMBL, FAERS, OFFSIDES, WHO ATC. Reason: highest score among the datasets that can answer the question; full facts, scores and limits in `docs/dataset_decision.md`. Judgement: we start from the labels' own text, so the system does the work SIDER's authors did by hand, and the measurements have something to measure.

**D-14, Database: PostgreSQL 16, not MongoDB, not SQLite.** → one flat `labels` table with a stored `tsvector` and a GIN index. Alternatives: MongoDB (the source is nested JSON with varying sections, 's NoSQL shape; it would be the better answer if we kept whole labels: rejected because we keep 13 fields of 29.8% of the labels and the work is counting and grouping, "Choose SQL when: reporting and aggregation are central"); PostgreSQL with the whole label in a `JSONB` column (rejected: about 2.6 GB for the usable labels, arithmetic estimate, against 127 MB flat); SQLite (no server: the course asks for a database service, and two programs use it). Reason from the shape in `docs/schema.md`.

**D-15, Processing in SQL, not pandas.** → the `drugs` table and the three queries are SQL in `sql/queries.sql`, read by name by the loader, the dashboard and the benchmark. Alternative: pull the matching labels into pandas and group there. Reason: "move the computation to the data" (template D-7); the database returns 25 rows, not thousands of long texts.

### Data and cleaning (Role A)

**D-16, Deduplication by `set_id`, newest version kept.** → `parse()` keeps one row per `set_id`; if a `set_id` comes twice, the row with the higher `version` wins. Alternatives: no check (the research found 262,907 distinct `set_id` in 262,907 labels: the export is already one row per label at its latest version, research counts in `docs/evidence/fp_sample.md` section 4); deduplicate by text, i.e. collapse labels with the same ingredient, product type and indications (78,472 → 33,606 rows, `docs/evidence/fp_sample.md` section 4: rejected, it would hide how many products and companies exist, which the answer reports as "labels"). Reason: a cheap guard for a weekly export we did not write. Measured: `duplicate_set_id=0` in every core run [M]. Judgement: the answer counts labels, and many labels are repackagers of the same product (dataset limit 5); the dashboard says "labels", never "drugs approved".

**D-17, Product type mapping.** → `openfda.product_type` "HUMAN PRESCRIPTION DRUG" → `Rx`, "HUMAN OTC DRUG" → `OTC`, any other value in title case ("Cellular Therapy", 18 labels at 100% [M]), "Unknown" if empty (0 rows, because a kept label always has the `openfda` block or a generic name). Alternatives: drop the other types (rejected: they are real labels with indications; dropping them silently changes counts); a `CHECK` constraint with two values (rejected: the FDA owns the vocabulary). Result at 100%: OTC 45,062, Rx 33,392, Cellular Therapy 18 [M], the same as the research counts (`docs/evidence/fp_sample.md` section 4).

**D-18, Cleaning rules, in the loader, while streaming.** → (1) drop a label with no or empty "Indications and usage" (11,921 [M]); (2) drop a label with no ingredient name (172,514 [M]); (3) names upper-cased and whitespace-normalised, then sorted and de-duplicated before joining ("Ibuprofen sodium " → "IBUPROFEN SODIUM"); (4) the indications paragraphs joined with one space, whitespace normalised (the text keeps its "1 INDICATIONS AND USAGE" heading: harmless for the search, visible in snippets); (5) `effective_time` parsed as a date, NULL if invalid (1 label [M]); (6) a date in the future kept (2026-11-23, 1 label [M]): it is what the FDA published. Every drop is counted in `pipeline_timings.detail` and `load_info`. Alternative: load everything and filter in SQL (rejected: 70% of the labels could never answer the question; "filter and select early"). Judgement on (4): removing the section heading was not worth a rule a student has to explain.

### Database and queries

**D-19, Text search configuration `'english'`.** → `to_tsvector('english', ...)` for the stored column and `phraseto_tsquery('english', ...)` for the query: lower case, English stop words removed, Snowball English stemming ("migraines" and "migraine" → `migrain`; the plans show `'''migrain'''::tsquery`, `core_queries_*.txt` [M]). Alternatives: `'simple'` (no stemming: "migraines" would not find "migraine"); `ILIKE '%migraine%'` (no stemming, no word boundaries, no index of ours can serve it: research measured 927 ms for migraine at 100%, and "depression" 858 labels against 2,652 with full-text search, `docs/evidence/fp_sample.md` section 5). Cost, Judgement: stemming can merge words that differ in meaning, and drug and disease names are not English words (not measured here); the research Python stand-in with the same stemmer gave the same counts as PostgreSQL for 9 of 10 conditions. The configuration must be the same in the column, the index and the query, or the index is not used.

**D-20, `phraseto_tsquery`, not `plainto_tsquery` or `websearch_to_tsquery`.** → the words of a condition must appear in order and next to each other (stop words aside): "type 2 diabetes" → `'type' <-> '2' <-> 'diabet'`. Alternatives: `plainto_tsquery` (all the words anywhere in the text: "type 2 diabetes" would also match a label about "type 1 diabetes" that mentions "2 tablets": more false positives); `websearch_to_tsquery` (quotes, OR, minus: more power, but the user must learn a syntax). For a one-word condition the three give the same query. Count difference for multi-word conditions: **to be measured** (not in any file yet).

**D-21, GIN index, kept; no other index on `labels`.** → one GIN index on `tsv` (D-10). Alternatives: no index (kept as `CREATE_INDEX=0` and as the benchmark's `without_index` mode: every stored `tsv` read, 70-140 ms at 100% on the research step's local PostgreSQL, `docs/evidence/fp_sample.md` section 5); a GiST index on `tsv` (smaller, but lossy: it must recheck rows, so slower reads; PostgreSQL documentation, not measured); a B-tree (cannot answer "contains this word"); `pg_trgm` for `ILIKE` (a different, unstemmed search). Reason: the planner uses GIN by itself for `@@`, and its cost is small and measured: 11.5 MB and 1.5 s at 100% [M].

**D-22, Three query modes for the measurements, not two.** → `with_index` (GIN), `without_index` (same query after `DROP INDEX`: the stored `tsv` is read row by row) and `on_the_fly` (`to_tsvector(indications)` in the query: the text is stemmed again on every row). Reason: they separate the two savings, "store the words once" (stored column vs on the fly) and "find without reading" (index vs scan), so each can be explained with its own lecture. Alternative: index vs on the fly only (rejected: it would credit the index with the saving of the stored column).

**D-23, No foreign key, one main table.** → `labels` is the only loaded table; `drugs` is computed from it. Alternatives: a foreign key `labels.substance_key → drugs` (rejected: `drugs` is built from `labels`, so the key could never fail, and it would force building `drugs` before the COPY it depends on); normalised `label_substance` / `label_route` / `label_class` tables (rejected for this question: the answer groups by the whole combination; it would be the first change for "which products contain aspirin?"). Details in `docs/schema.md`.

### Docker (Role D)

**D-24, Non-root user in both images, UID 1000.** → `useradd --uid 1000` and `USER loader` / `USER app`. Consequence: on Linux, `./data` must be writable by UID 1000; the README says what to do otherwise. On the cloud VM, `data/raw/` holds hard links to the research zips (D-7), which share their owner with the originals: a `chown -R` of a test copy briefly changed the owner of the research files, and it was set back by hand (core report). Judgement: on a laptop there are no hard links and nothing of this happens.

**D-25, The data cache is a bind mount, the database a named volume.** → `./data:/data` for the downloaded zips (the user can see, delete or reuse them), `dbdata` for PostgreSQL. Alternatives: download into the image (rejected: 1.86 GB in every build, and data in an image); a named volume for the zips too (rejected: invisible to the user, and `down -v` would delete 1.86 GB of downloads with the database). Reason: a benchmark that empties the database between runs (`down -v`) must not download 1.86 GB again each time.

### Measurements (Role E)

**D-26, Predictions merged before the measured runs.** → `measure/predictions.md` was committed and merged into `main` (`3473d39`, 14:59) before `measure/benchmark.py` ran the measured protocol (started 15:05:57, `benchmark_log.txt`; results `bdc6106`, 15:27). Per the course: "Predict, then verify." Known numbers it starts from (core test, research report) are listed in it as "known before writing", with their files. One benchmark test run (25%, 1 run) happened before the predictions, and its full_run 77.1 s, parse 65.3 s and on-the-fly 1.2-1.5 s were written in `measure/how_to_reproduce.md:54` (`7cd4066`, 14:54), before `predictions.md` (`3473d39`, 14:59). The 25% predictions P1, P7 and P14 may have been influenced by it. (Corrected after review: this entry first said the test run's outputs "were not opened".)

**D-27, The parse is not made faster before the benchmark.** → the benchmark measures the loader as it is: all 14 zips parsed at every size (D-3). Alternatives considered, all left for after the measured runs, because each changes what the 25/50/100% load times mean: (a) a cleaned extract of all buckets cached in `data/` on the first run (the sizes would then read the kept rows, about 13-52 MB of text by prediction, instead of 8.75 GB of JSON); (b) parse the 14 files in parallel, one process per file, on 4 cores (prediction, Judgement: about 3× faster at best, Amdahl, with the memory of 4 parsers); (c) build Python objects only for the kept sections (ijson's tokeniser must still read every byte, so the saving is the dict building only; not measured). Reason: "change one thing at a time"; the serial part is itself a finding to show, not to hide. After the measured runs, (a) was built and measured: D-29.


## What we changed and why, first round (5 Nov, evening)

When we read the whole repository again, we found gaps. On the system itself, some choices had never been measured and some failure paths had never been run. We measured them, one change at a time, and then ran the whole benchmark again (v2, `measure/results_v2/`). v1 stays in `measure/results/` as the "before". There was also one comment fix: `sql/schema.sql` now quotes this project's query times, not the research step's.

### Database and queries

**D-28, Full-text index: the stored `tsv` column stays; a GIN expression index was measured and rejected.**

- **Alternative** : no stored column. The index is built on the expression `to_tsvector('english', indications)`, and every query repeats that expression.
- **How it was measured:** one change, `TSV_MODE=expression`, a measurement mode only. `measure/gin_expression.sh` ran 3 loads per mode at 25% and at 100%, in the order A B B A A B, each on a fresh volume and from the extract.
- **Results** are in `measure/results_experiments/gin_expression/summary_table.txt`, with the plans in `explain/`. At 100%, stored column → expression index:

| Step | Stored column | Expression index |
|---|---:|---:|
| COPY | 10.72 s | 1.42 s |
| Index build | 1.40 s | 10.84 s |
| ANALYZE | 1.23 s | 4.55 s |
| Pipeline | 14.96 s | 18.44 s |
| Database | 138.1 MB | 88.7 MB |
| … heap | 71.8 MB | 54.3 MB |
| … TOAST | 40.5 MB | 9.0 MB |
| … GIN index | 11.50 MB | 11.09 MB |
| Migraine query | 1.86 ms | 1.90 ms |
| "type 2 diabetes" query | 10.4 ms | 470.4 ms |

The query times are means of 9 (3 loads × 3 repetitions). Both modes give the same answers: 680 labels / 48 ingredients for migraine, 1,337 / 66 for "type 2 diabetes". At 25% the pattern is the same: COPY 2.75 → 0.36 s, database 41.3 → 29.0 MB, phrase query 4.26 → 125.8 ms.

- **Why the phrase query is 45× slower** (arithmetic): the GIN index finds 1,480 candidate labels and cannot check word order. PostgreSQL rechecks each candidate on the row and drops 143 of them, in both modes. With the stored column, that recheck reads the stored words: the Bitmap Heap Scan takes 9.5 ms. With the expression index, it must stem each candidate's text again: 447.5 ms (`explain/100pct_*_type_2_diabetes.txt`). A one-word query needs no recheck, so migraine does not change.
- **Why ANALYZE is slower:** probably because PostgreSQL also gathers statistics on the index expression, which stems the sampled rows again (Judgement, not checked).
- **Decision:** keep the stored column. The user waits for every search, and any condition of more than one word, such as "type 2 diabetes" or "rheumatoid arthritis", is a phrase and pays the recheck. The load does not get shorter either: the pipeline is 3.5 s longer (arithmetic), because the index build stems every label after COPY. The saving is 49.4 MB of disk (arithmetic), less than the 74.4 MB extract we chose to keep (D-29). There is also one more rule to explain: every query must repeat the exact expression, or the index is not used (PostgreSQL documentation, not measured).

**D-29, Extract cache: the zips are parsed once.** (v2. In v3 the file is named `labels_<export_date>_<clean_version>.csv` (D-43), and a later start no longer needs the zips (D-44).)

- **What the loader does:** on a first start it parses the 14 zips and writes every usable row, all four buckets, once to `data/clean/labels_<export_date>.csv`. The file is written as `.part` and then renamed. Later starts read the file (step `read_extract`) and keep the sample's buckets. `EXTRACT_CACHE=0` forces the parse. This builds D-3 (a) and D-27 (a), which were rejected "for now" before the benchmark.
- **Reason:** the Cost question: every start re-parsed 8.75 GB of JSON to load 54.4 MB of text.
- **Measured** in benchmark v2 (`measure/results_v2/summary.csv`, means of 3), against v1 (`measure/results/summary.csv`):

| Later start | 25% | 50% | 100% |
|---|---:|---:|---:|
| Getting the rows, v2 (`read_extract`) | 1.00 s | 1.10 s | 1.25 s |
| Getting the rows, v1 (`parse`) | 63.32 s | 66.52 s | 67.43 s |
| Full run, v2 | 11.71 s | 14.82 s | 21.32 s |
| Full run, v1 | 74.34 s | 81.68 s | 89.74 s |

- **First start at 100%:** `parse` 59.07 s + `write_extract` 1.45 s, full run 81.48 s.
- **Same rows both ways:** the md5 of `labels` and of `drugs` is the same on the parse path and the extract path, at 100% and at 25% (`docs/evidence/v2_second_start_100pct.txt`, `v2_second_start_25pct.txt`).
- **Cost:**
  - 74.4 MB of disk (74,388,073 bytes, 4.0% of the zips, arithmetic).
  - The extract is read in full at every size (`rows_in_extract=78472` at 25%), so `read_extract` is nearly flat too.
  - A parse now holds all four buckets before it takes the sample, so a 25% parse peaks at 178 MiB RSS. In v1 it was 74 MiB (`v2_second_start_25pct.txt`; `core_loader_25pct.log`).
- **The staleness D-3 feared:**
  - The file name carries the export date, so a new export gets a new file.
  - A half-written extract stays a `.part` and is never read (case c4 in `docs/evidence/v2_corrupt_zip.txt`).
  - A wrong header stops the loader with a message.
- **Alternatives:**
  - Parquet. Rejected: it needs pyarrow in the loader image, while the `csv` module is standard library and the file loads by hand with `\copy` (Judgement).
  - Skip the load when the volume already holds this export. Rejected: `docker compose up -d --no-deps db app` already starts without a load, with no code (`docs/evidence/v2_restart_no_deps.txt`).

**D-30, One transaction for the whole load, and TCP keepalives on the loader's session.**

- **What changed:** TRUNCATE, COPY, the GIN build, `drugs`, ANALYZE and `load_info` now run in one transaction with one COMMIT. `pipeline_timings` goes in a second, small transaction after it.
- **Why:** v1 committed `labels` before the index and `drugs` were built. A crash in between would leave labels without an index and an empty `drugs` table .
- **Test** (`docs/evidence/v2_atomic.txt`): after a complete load at 100%, `docker kill` of a new loader during its COPY.
- **Attempt 1 found a second problem.** PostgreSQL never saw the connection close. The dead session stayed in COPY for 5.5 minutes, holding TRUNCATE's lock, so every read of `labels` waited. `tcp_keepalives_idle = 0` means the OS default, which is 2 hours on Linux.
- **The fix:** the loader connects with `tcp_keepalives_idle=10`, `tcp_keepalives_interval=5` and `tcp_keepalives_count=3` for its own session.
- **Attempt 2:**
  - The dead session was gone 25.5 s after the kill, and its work was rolled back.
  - The previous load was complete: 78,472 labels, 8,157 drugs, both indexes, the same md5.
  - During those 25.5 s, a read with `lock_timeout = 1s` was cancelled. The dashboard reads `labels` only after the loader exits, except on the `--no-deps` path.
- **Alternative** (the second option): write a "complete" row last, and have the app refuse to draw without it. Rejected: one transaction needs no extra rule in the app (Judgement).

**D-31, A missing `tsv` column is added back; other schema changes need `down -v`.**

- **What the loader does:** after TRUNCATE it checks `information_schema`. If `labels` has no `tsv` column (a volume made by an older `schema.sql`, or a column dropped by hand), it logs a line and adds the generated column back before COPY. For other schema changes the README says to run `docker compose down -v` first.
- **Test** (`docs/evidence/v2_self_heal.txt`, at 25%):
  - **Part 1:** a `TSV_MODE=after` run, then a default run. Both exit 0, and the repair is not needed: `tsv_fill` adds the column back. v1 already had the same code in `loader/load_fda.py`, so the failure we had suspected, a `tsv` left dropped by an `after` run, does not happen.
  - **Part 2:** `tsv` dropped by hand, then a default run. The loader logs "labels has no tsv column ... adding it back before COPY", builds the GIN index and exits 0: migraine 160 labels / 19 ingredients.
  - **What v1 would do in part 2:** fail at `CREATE INDEX` with exit 1 (a prediction from the v1 code, not run).
- **Alternative:** a migration tool. Rejected for one column of one table (Judgement).

### Data and loading (Role A)

**D-32, Stale manifest: a size mismatch re-checks the live manifest.** (v2 covered only a zip present with the wrong size. In v3 the same check also runs for a zip that was missing and has just been downloaded (D-45).)

- **What the loader does** when a cached zip's size does not match the cached `download.json`: it fetches the live manifest (`f7e5a2a`, the review's reliability gap 1).
  - Same `export_date`: it downloads that one file again, once.
  - A new `export_date`: it stops with "openFDA published a new export (<date>); delete data/raw and data/clean and run again".
- **Tests** ran on copies of the zips (not hard links) in a temporary data folder (`docs/evidence/v2_corrupt_zip.txt`):
  - **c1:** partition 14 cut to 10 MiB. It is downloaded again, byte-identical, and the load exits 0. v1 stopped with exit 1 here (D-6).
  - **c3:** the cached manifest edited to `export_date` 2026-10-29. The new-export message, exit 1, after 1.6 s.
  - **c2:** a zip of the right size with a broken directory. "not a readable zip", exit 1, and the database is untouched. The first c2 used a wrong `dd` offset; it is kept in the file with the correction.
  - **c4:** leftover `.part` files, of a zip and of the extract. They are never taken for finished files, and both are rebuilt byte-identical.
- **Alternative** : keep each export under `data/raw/<export_date>/`. Rejected: 1.86 GB of an old export would stay on disk without the user noticing (Judgement).

**D-33, Lock files for both images.**

- **What changed:** `app/constraints.txt` (36 packages) and `loader/constraints.txt` (4 packages) are the `pip freeze` of the images built on 5 Nov 2026. Both Dockerfiles install with `-r requirements.txt -c constraints.txt` (`ffdd697`).
- **Why:** `requirements.txt` pinned only the direct libraries, so Streamlit's indirect dependencies could change on a rebuild .
- **Test** (commit message of `ffdd697`): a `--no-cache` build of the app took 121.6 s, and `pip freeze` of the new images equals the constraints files.
- **Limit:** the constraints come from a 16:40 build, not from the image of the v1 runs (the header of each file).
- **Alternative:** pip-tools or poetry. Rejected: a new tool, where `pip freeze` and `-c` are pip's own (Judgement).

### Output (Role C)

**D-34, The drill-down follows the Rx/OTC choice.**

- **What changed:** `labels_for_drug` takes `%(product_type)s`, like `drugs_for_condition` (`2d103b4`). We found this ourselves.
- **Before:** with "Prescription (Rx)" chosen, the page said "9 of 1 labels" and listed OTC labels too. With "OTC" it said "9 of 8".
- **After:** "1 of 1" and "8 of 8". "All" is unchanged at 9 of 9 (`docs/evidence/v2_drilldown_filter.txt`, Streamlit AppTest at 25%, "acne", ADAPALENE).
- **The benchmark** passes `'all'`, so it measures the same query as v1.

### Measurements (Role E)

**D-35, Parallel scan: why the scan without the index has no worker. Settings unchanged.**

- **Measured** at 100% (`measure/parallel_scan.sh`; `measure/results_experiments/parallel_scan/run.txt` and `stats.txt`; `ab3ac31`).
- **What the planner knows:**
  - `labels` has 8,768 pages and 78,472 rows.
  - Its TOAST table has 0 pages in `pg_class`, although it holds 39.9 MB. Judgement: the planner prices the heap and not the long values in TOAST that the scan also reads. That would fit v1's plan reading 46,915 + 100 buffers for 8,768 heap pages.
  - The settings are the defaults: `parallel_setup_cost` 1000.
- **The cost estimates:**
  - The scan costs 9,748.90 serial against 9,176.71 with 2 workers. Workers save only 572 units, because the disk part of the cost (8,768 pages) is not divided among them (arithmetic).
  - The whole plan costs 10,015.70 serial against 9,487.51 with `parallel_setup_cost = 0`. With the setup cost of 1000 put back, the parallel plan costs 10,487.51 (arithmetic), so the setup cost alone keeps the workers out.
  - On the fly, `to_tsvector` costs 100 × `cpu_operator_cost` per row. Workers save 12,016 units of the scan (29,366.90 against 17,350.88, arithmetic), so the planner uses them.
- **Timed without the index**, default settings → the three parallel settings at 0:
  - In the database: 82.1 → 46.8 ms (1.76×).
  - From Python: 90.2 → 44.0 ms (2.05×).
- **The index** speeds up the query 46.5× both ways (1.77 / 1.94 ms). The user waits for the Python time, round trip included. This answers the review's "is 37× what the database sees?" for v2.
- **Decision:** keep the defaults. The index already removes the scan, and the parallel costs are server-wide settings for a path the app does not take (Judgement).

**D-36, App memory, measured while a browser uses the page.**

- **How:** `measure/app_memory.py` drives Chromium through Playwright, with `measure/app_memory.js`: 16 searches at 100%, each with its drill-down, in 41.5 s, with 0 page errors. `docker stats` samples every 0.5 s, but the samples land in pairs, so the real resolution is about 1 s (`measure/results_experiments/app_memory/output.txt`, `peaks.csv`; `f0bcd60`).
- **Why:** v1 read the app's memory while it served no search (P32).
- **Results:**
  - `app`: idle median 46.5 MiB (max 52.4), peak 138.4 MiB while serving, 132.8 MiB median after the browser closed. Judgement, not checked: Streamlit keeps the session and its cached data after the visit.
  - `db`: idle median 168.1 MiB, with one unexplained spike to 208.2 MiB at 93.7% CPU and no browser connected. Peak 217.8 MiB while serving.
- **Decision:** no code change. The README reports the browser peak.

**D-37, The v1 round effect: reported, v1 unchanged.**

- **Measured** with `measure/round_effect.py` on v1's `raw_runs.csv` (`measure/results_experiments/round_effect/output.txt`, `by_round.csv`; `8de5e1e`).
- **Round 1 minus the mean of rounds 2-3,** at 25 / 50 / 100%:
  - `parse`: +6.18 / +7.37 / +6.20 s.
  - `full_run`: +6.94 / +7.67 / +8.94 s.
- **Why the size comparison holds:** each size ran once in each round and once in each position, so round 1 is inside every size's mean once.
- **The spread is mostly this effect:** taking it out lowers the `parse` std from 4.40 / 4.32 / 3.75 to 2.34 / 1.08 / 1.37 s.
- **The parse stays nearly flat** within one round: it grows +6.1%, +13.3% and +0.7% from 25% to 100% (D-3).
- **The cause is unknown on the shared VM.** Round 1 at 25% had the lowest load average (0.21) and was still the slowest 25% run.
- **Alternative:** drop round 1. Rejected: every run is reported.

**D-38, Benchmark v2 protocol.**

- **What stays from v1:** 3 sizes × 3 runs, interleaved and rotated, with a fresh volume and an emptied OS file cache before every run.
- **What changed** (`dcb6643`; `measure/how_to_reproduce.md`):
  1. `data/clean` is kept between runs, like `data/raw`, so the 3 × 3 series measures a normal later start. Each run checks that the loader took the path its mode names, and the benchmark stops if not.
  2. `--first-start 3`: three runs at 100% that delete `data/clean` first, so the loader parses and writes the extract again.
  3. The queries also get per-run means (`runs`, `run_mean_mean`, `run_mean_std`), because the pooled n = 9 std mixes the spread within a run and between runs . For the migraine query with the index, the pooled std is 0.415 / 0.333 / 0.400 ms and the std of the 3 per-run means is 0.270 / 0.249 / 0.357 ms.
  4. The load average is read twice. Before `down -v` it was 1.69 / 1.68 / 2.30; after a 30 s settle, 1.03 / 1.08 / 1.39. In the first starts it was 1.25 → 0.83.
  5. `--extra-tsv-after` is removed. It was measured in v1 (D-9), and in v1 it always ran last in its round .
- **The run:** alone on the VM, 17:57-18:14 UTC, 1019 s, project `drug-explorer` (`c467927`).
- **Same answer:** `check_same_answer_migraine` = 1 at every size, and migraine gives 680 labels at 100%.
- **Limit:** the first starts ran after the 3 × 3 series, not interleaved with it, so 81.48 s against v1's 89.74 s is not like for like. Part of the 8.3 s gap may be v1's round-1 slowdown (Judgement, D-37).

### Choices that had no alternative written down

**D-39, Output: a Streamlit dashboard, not a static HTML report or a notebook.** offers three outputs: "A dashboard, a report, or a notebook. (Streamlit, Jupyter)".

- **A static HTML report written by the loader.** It would remove the third long-running container: the 829 MB app image (`measure/results_v2/machine.txt`), the 121.6 s no-cache build (D-33) and 46.5-138.4 MiB of memory (D-36). Rejected: the question takes a condition the user types, and a static report can hold only conditions chosen in advance. The drill-down, one ingredient's labels with the matching words highlighted, would also need a page per pair (Judgement).
- **A Jupyter notebook.** Rejected: the user would need a kernel, either a Python install or a notebook server container, and the cells must be run in order (Judgement).
- **Reason:** the answer is interactive, and the page runs the real queries on every search, so the query times it shows are live (`app/dashboard.py`, the uncached `with connect()` blocks).
- **Cost:** the largest of the three images, as said above.

**D-40, The benchmark client runs in the loader image.**

- **How:** `measure/benchmark.py` runs `docker compose run --rm --no-deps loader python bench_queries.py`. `loader/Dockerfile` copies `loader/*.py`, so the loader image also carries `bench_queries.py`, 9,901 bytes (cosmetic).
- **Reasons:**
  - The client must reach `db` by name on the compose network, and `db` publishes no port.
  - The loader image already has the same Python 3.12.16 and psycopg 3.3.6 (`machine.txt`), so no extra image is needed, and no Python driver on the host.
- **Alternatives:**
  - A fourth `bench` service with its own Dockerfile. Rejected: one more image to build and explain, for one script (Judgement).
  - The host, with `db`'s port published. Rejected: that breaks the rule above.
  - The app image. Rejected: the client's memory would then be counted in the `app` container, which we measure.
- **Cost:** about 10 kB of code the loader never runs.

**D-41, `prepare_threshold = None` in the benchmark.**

- **Where:** `loader/bench_queries.py`, and the v2 experiments `measure/gin_expression_queries.py` and `measure/parallel_scan.py`, turn off psycopg's automatic prepared statements.
- **Reason:**
  - psycopg 3 prepares a query on the server after it has run 5 times on one connection, and PostgreSQL may then switch to a generic plan (psycopg and PostgreSQL documentation, not measured here).
  - The benchmark runs `drugs_for_condition` 40 times on one connection: 5 conditions × (1 warm-up + 3 timed), with the index and then without it (`REPS`). Without the setting, most timed runs would measure a prepared statement.
  - The dashboard opens a connection for each page run and runs each query once on it (`app/dashboard.py`), so it never reaches the threshold. With the setting, each timed run is planned like one dashboard call.
- **Alternative:** keep the default. Rejected: the timed runs would no longer measure what a user waits for.
- **Not measured:** the difference between the two.

**D-42, Base image tags stay `postgres:16` and `python:3.12-slim`.**

- **Reason:** these are the tags in the course's own files (the ex4 solution DK-12 and C-04), and they meet 's rule "Pin base tag and libraries, never latest".
- **The point:** the tags move with minor and patch versions.
- **Alternative:** a patch tag such as `postgres:16.15`, or a registry digest. It is stricter, and allowed. Rejected here because Docker Hub refuses pulls On the cloud VM (`docs/environment.md`, item 2), so a new tag could not be pulled and tested.
- **What we did instead:**
  - `machine.txt` records the exact image ids and versions behind every number: PostgreSQL 16.15, Python 3.12.16.
  - The libraries, direct and indirect, are fixed by the constraints files (D-33).
  - Both tags are multi-arch with arm64: checked from the cloud VM, not on a Mac (`docs/evidence/arm64_check.txt`).
- **The VM base image:** on this VM, `python:3.12-slim` is a VM-only variant: the official image plus the proxy's CA bundle, so that pip can verify TLS inside a build (`docs/environment.md`, item 3). The Dockerfiles name the official image, which a laptop pulls. Expected effect on the measurements: none (Judgement, not measured).

## What we changed and why, second round (5 Nov, night)

A second reading of the whole system found two failure paths that the v2 fixes had missed, a cache that could serve old rows, and numbers that were asserted instead of measured. v3 fixed or measured each one, one change at a time, and the benchmark was fixed and its v3 predictions written before it ran. v1 (`measure/results/`) and v2 (`measure/results_v2/`) stay unchanged as the "before"; benchmark v3 writes `measure/results_v3/`. Benchmark v3 has run; its numbers are from `measure/results_v3/summary.csv`.

### Data and loading (Role A)

**D-43, The extract's name carries a version of the cleaning rules.**

- **What changed** (`3ce6b20`): the extract is `data/clean/labels_<export_date>_<clean_version>.csv`. `clean_version` is 8 hex digits of an md5 over the source of `norm`, `first`, `bucket`, `clean` and `parse`, plus `COLUMNS` and `PRODUCT_TYPES` (`loader/load_fda.py:321-327`). A changed rule gives a new name, so the next start parses the zips again. The loader names any other extract it finds and never deletes one: "data/clean also holds ... not used; delete to free the disk" (`load_fda.py:446`).
- **Why** (round 2): v2 keyed the extract by the export date only. After a change to `clean()`, a later start read the old rows, and nothing told the user.
- **Test** (`docs/evidence/v3_extract_key.txt`, at 25%, on copies; the zips mounted read-only), with the generic-name fallback removed from `clean()` as the test change:
  - **k0, `main` before v3:** the changed rule, but the old extract is read: `kept=19546`, the count with the fallback. Exit 0 in 5.2 s, silently stale.
  - **k1, v3, unchanged code:** the v2 file `labels_2026-11-05.csv` is not read. The zips are parsed (71.1 s wall), and `labels_2026-11-05_e2adc54e.csv` is written. `cmp` finds it byte-identical to the v2 file, 74,388,073 bytes: the rules did not change, only the name.
  - **k2:** a later start reads the new file (7.5 s wall).
  - **k3, v3, changed rule:** `clean_version=4805b507`, so a parse: `kept=19202`, `name_from_generic_name=0`, 3,377 drugs, a new extract of 72,784,063 bytes, 67.7 s wall.
  - **k4:** back to the committed code: its own extract is read again, `kept=19546`.
- **Alternatives:**
  - A version constant bumped by hand. Rejected: the bump is the step that gets forgotten (the code comment, `load_fda.py:314-319`; Judgement).
  - A README line, "after changing `loader/load_fda.py`, `rm -rf data/clean`" (the second option). Rejected: it relies on the same memory.
  - The hash in the CSV header instead of the name. Rejected: a header is read only after the file is opened, while a name shows on `ls` which rules each file holds (Judgement).
- **Price:** an edit of a comment inside those five functions also changes the hash and costs one parse: 59.07 s at 100% (`measure/results_v2/summary.csv`, `first_start`, `parse`). Old extracts stay on disk, 74.4 MB each, until the user deletes them.

**D-44, With the extract of this export, a later start does not need the zips.**

- **What changed** (`e2cbfe7`): `download()` reads the manifest (the cached one, or fetched when `data/raw` is gone), then returns before the zip loop when `labels_<export_date>_<clean_version>.csv` exists and `EXTRACT_CACHE=1` (`load_fda.py:197-201`). No zip is downloaded, opened or size-checked. `load_info.downloaded_on` falls back to the extract's date when the zips are gone (`load_fda.py:520-525`).
- **Why:** the review's Cost question, deeper (round 2, Q1 and finding 7): the extract is 74.4 MB, but v2's later start still needed all 1.86 GB of zips, because `download()` checked every zip before the loader looked for the extract. The README test found the same line wrong.
- **Test** (`docs/evidence/v3_extract_without_zips.txt`, at 100%, a folder holding only a copy of the extract):
  - **e1:** no `raw/` at all. The manifest is fetched (601,654 bytes), and the zips are "not needed, not checked". Exit 0, 78,472 labels and 8,157 drugs, as with the zips. 18.7 s wall; `download` 0.69 s, `read_extract` 1.26 s, pipeline 15.85 s.
  - **e2:** the manifest of e1 is reused. 16.4 s wall; `download` 0.00 s, `read_extract` 1.10 s, pipeline 14.43 s.
  - **Disk for a later start:** 74,989,727 bytes (the extract and the manifest), against 1,933,295,489 bytes with the 14 zips: 25.8 times less (arithmetic).
  - **e3:** the manifest cannot be fetched (a dead HTTPS proxy for that container) and an extract exists. 5 retries, then exit 1 after 66.6 s, with a message that names the extract. The database keeps the load of e2.
- **Alternatives:**
  - Keep v2's order, so the zips must stay. Rejected: 1.86 GB kept on disk to protect files a later start does not read.
  - Load the extract when the manifest cannot be fetched. Rejected: without the manifest, the loader cannot tell whether openFDA has published a newer export since the extract was written, so loading it would be a guess (Judgement, in the code comment at `load_fda.py:184-186`). With `data/raw/download.json` kept, a later start needs no network at all (e2).
- **Price:** a later start no longer re-verifies the zips. They are read, and checked as before, only by the next parse: a new export, or changed rules (D-43). Time: none measurable. `download` was 0.0116 s at 100% in v2 with the zip checks (`measure/results_v2/summary.csv`) and 0.006-0.009 s in v3 without them (`docs/evidence/v3_startup_breakdown.txt`).

**D-45, A zip downloaded just now with the wrong size re-checks the live manifest too.**

- **What changed** (`366defc`): the check of D-32 moved into `same_export_or_stop` (`load_fda.py:143-156`), and it also runs when a zip that was missing (or only a `.part`) has just been downloaded and its size does not match the cached manifest (`load_fda.py:215-221`). A new export stops with the same "openFDA published a new export ... delete data/raw and data/clean" message as D-32. The same export with a wrong size removes the file and says "Try again later".
- **Why** (round 2, her presentation question): a download cut on Monday leaves only a `.part`. On Thursday openFDA publishes a new export. The cached manifest's URL now serves Thursday's file, of another size. v2 took the plain-download branch and stopped with "Delete it and run again", and doing that repeated the same failure.
- **Test** (`docs/evidence/v3_missing_zip.txt`, on copies of partitions 1-13, a hand-edited copy of the manifest, and a 10 MiB `.part` of partition 14):
  - **m1, `main` before v3:** "Delete it and run again", exit 1 in 1.6 s. After deleting it: the same message in 1.2 s. A loop.
  - **m2, v3:** "openFDA published a new export (2026-11-05)", exit 1 in 3.0 s.
  - **m3, v3, same export, sizes disagree:** the file is removed, "Try again later", exit 1 in 2.6 s.
  - **m4, m5, controls:** the unedited manifest with partition 14 missing, and a zip present but cut to 10 MiB (v2's case c1 again). Both are downloaded, byte-identical (`cmp`), and loaded: exit 0 in 66.5 s and 66.6 s.
- **Alternative** (the second option): compare the export date with the live manifest before downloading any missing file. Rejected: one rule for both cases, "a size that does not match the manifest", in one function. A first start with nothing wrong makes no extra request (Judgement).

**D-46, An HTTP 4xx answer is not retried.**

- **What changed** (`53b370c`): in `http_get`, an `HTTPError` with a code from 400 to 499, except 429 ("too many requests"), stops at once with "download refused, HTTP <code>, not retried: <url>" (`load_fda.py:110-113`). Refused connections, timeouts and cut bodies are still retried.
- **Why** (round 2, cosmetic): `HTTPError` is a kind of `URLError`, so v2 asked six times, with backoff, for a URL the server had refused, about a minute.
- **Test** (`docs/evidence/v3_http_4xx.txt`): the manifest copy edited to point partition 14 to a file that does not exist (HTTP 403 from download.open.fda.gov). `main` failed after 6 attempts in 67.3 s; v3 failed at the first answer in 2.1 s.
- **Not tested:** a 5xx answer.
- **Alternative:** retry every error, as in v2. Rejected: a 4xx is the server's answer about the request, so the same request gets the same answer (Judgement). asks for "Retry after growing, randomised waits (as above), so that clients do not all retry at the same moment." That stays for the errors where a second try can succeed.

**D-47, The retry path and "the app never starts after exit 1": run, no code changed.**

- **Why** (round 2): both were only argued in v2. Every failure test ran the loader alone (`run --no-deps`), and no retry had ever been logged.
- **Retries** (`e817dce`, `docs/evidence/v3_retry.txt`): the loader with no network (a dead HTTPS proxy) on an empty data folder. 5 retries announce waits of 2.2 / 4.8 / 9.0 / 16.2 / 32.4 s, and the measured gaps between the lines are the same to 0.02 s. The rule in the code is `min(60, 2**attempt) + uniform(0, 1)`. Exit 1 after 64.61 s.
- **The app under `docker compose up`** (`docs/evidence/v3_app_waits_for_loader.txt`):
  - The README tester's run (part 1): `data/` owned by root, step 4 skipped. The loader fails with `PermissionError ... '/data/raw'` and exits 1, compose prints "service "loader" didn't complete successfully: exit 1" and exits 1, and the app stays "Created".
  - Our run (part 2), no network: the same. `docker inspect` gives the app `status=created` and `started_at=0001-01-01T00:00:00Z`, Docker's zero time, and port 8581 refuses the connection.
  - In both, `db` is left running ("Up About a minute (healthy)"), and `docker compose down` removes it.
- **Decision:** no change. `db` left running holds no wrong data, and `down` is the README's stop command (Judgement).
- **Alternative:** `docker compose up --abort-on-container-exit`. Rejected: it stops every container when any one exits, and the loader exits on every normal start, with 0, so the app would stop too (Docker documentation, not tested).

### Docker (Role D)

**D-48, Linux UID: step 4 (`chown`) stays; its failure path is now tested.**

- **The point** (round 2, finding 5 and Q4): the loader runs as UID 1000 and writes the bind mount `./data`, so a Linux user with another UID needs `sudo chown 1000 data`, and the path without it was "read from the code, not tested".
- **Tested** by the README tester, not by us: the loader exits 1 with `Permission denied: '/data/raw'`, and the app is never started. So the README claim holds, plus one fact it did not say: `db` stays up (D-47).
- **Alternatives:**
  - `user: "${UID:-1000}:${GID:-1000}"` on the loader. Not built. Judgement, not tested: bash sets `UID` but does not export it, and sets no `GID` at all, so Compose would see both only if the user exports them first: one manual step in place of another.
  - A second named volume for the zips and the extract. Rejected for the reason of D-25: the user cannot see the files, and `down -v` would delete 1.86 GB of downloads.
- **Decision:** keep step 4. The README's "Linux, chown skipped" line is updated in the README's own round.

### Database and queries

**D-49, A reload holds readers for the whole load: measured, not redesigned.**

- **The question:** TRUNCATE takes ACCESS EXCLUSIVE on `labels` and holds it until the one commit (D-30, `load_fda.py:467` to `:548`). What does the page do while `docker compose run --rm loader` reloads, and for how long? Before this measurement our answer was "about 13 s (arithmetic on summary.csv, not measured)".
- **Measured** (`docs/evidence/v3_reload_lock.py` and `.txt`, at 100%, 2 runs): a probe in the app container runs `drugs_for_condition('migraine', 'all')` every 0.5 s on a new connection while the loader reloads.
  - The lock window, from the start of `schema_and_truncate` to the end of `commit` on the loader's clock: 16.190 s and 14.584 s.
  - One read per run waited: 15.800 s and 14.332 s. The probe is one reader, so the next reads queued behind it.
  - Every other read took 17-38 ms.
  - Every read returned 25 rows: a reader never saw the emptied table. It waited, then saw the new load. a transaction is "a group of changes that happens completely, or not at all."
- **Alternative** : load into `labels_new`, build its index and the `drugs` rows, ANALYZE, then swap the tables with `ALTER TABLE ... RENAME` in one short transaction. Readers would then wait only for the renames (a prediction, not measured). Not built. The price: twice the table on disk during the load, index and constraint names to manage, more loader code.
- **Decision:** not changed (Judgement: right size). The app starts only after the loader has exited 0 (`service_completed_successfully`), so a normal start makes nobody wait. Only a reload by hand while the page is open does, for about 15 s at 100%, once.

**D-50, The fixed part of a later start: measured; the healthcheck unchanged.**

- **The question:** 4× the data takes 1.82× the time, with 6.65-6.88 s that do not grow. What is in that fixed part, and how much of it is the 3 s healthcheck interval? v2 named "containers, healthcheck, Streamlit" without measuring them.
- **Measured** (`docs/evidence/v3_startup_breakdown.py` and `.txt`): 3 later starts at 100% with the benchmark's protocol, split with `docker events`, the loader's step log and HTTP polled every 0.05 s.
  - `full_run` 23.62 / 22.14 / 23.76 s; `full_run − pipeline_total` 6.90 / 7.07 / 7.10 s. The 9 phases outside the pipeline add up to the same values within 1 ms: the fixed part is fully attributed.
  - Largest: from db start to db healthy, 3.11 s (44.3%). The database's own log splits it (run 3): ready to accept connections 1.49 s after the start, then 1.60 s more until the first `pg_isready` probe, which Docker runs one interval (3 s) after the container starts.
  - Then Streamlit's start, 1.31 s (18.7%), and db healthy to loader started, 0.59 s (8.4%). The other six phases are each 0.49 s or less.
  - The page itself (`/`) answered 0.004-0.007 s after `/_stcore/health`.
- **Amdahl, with the measured parts:** at 100%, the fixed part is 7.02 s of a 23.17 s start, 30% (arithmetic, means of the 3 runs). "Practical reading: before buying machines, measure which fraction of the job cannot be parallelised. That number is your ceiling."
- **Alternative:** a healthcheck `start_interval`, so that the first probe comes sooner during `start_period`. That could save most of the 1.6 s wait (Judgement, not measured). Not done: the one-command start does not need it, and the course's compose files do not use it.

### Measurements (Role E)

**D-51, `docker stats`: one reading is written once.**

- **What changed** (`d794808`): two overlapping `docker stats --no-stream` calls that finish in the same pass return the same daemon reading. It is now written once (`measure/benchmark.py`, `MemorySampler`).
- **Why** (round 2, cosmetic): v2's `docker_stats_samples.csv` held every sample twice, 2,791 rows of which 1,413 are distinct (we counted the same: arithmetic on that file). The docs said "a new sample every 0.5 s", while distinct readings are about 1 s apart.
- **Effect:** the peaks do not change (the maximum of a reading and its copy is the same reading). `measure/how_to_reproduce.md` now says "about 1 s apart". v2's file is left as it is.
- **Alternative** (the other option): one call at a time. Rejected: one call takes about 2 s (the class docstring), so samples would be about 2 s apart.

**D-52, Benchmark v3: predictions first, the v2 protocol unchanged.**

- **Predictions** (`dcbefbf`, committed at 20:27:31 UTC; the first file the benchmark wrote, `measure/results_v3/machine.txt`, has the time 20:27:53): `measure/predictions_v3.md`, 28 values with ranges, each marked **v2**, **v3ev** (the v3 evidence files above) or **new**. Round 2: nothing was predicted before benchmark v2.
- **Protocol:** the same as v2 (D-38): `python3 measure/benchmark.py --drop-caches --first-start 3 --out measure/results_v3`. 3 sizes × 3 runs of the later start, interleaved and rotated, then 3 first starts at 100%. The timed pipeline is the v2 pipeline, so the main prediction is "no change beyond run-to-run noise". Only the `download` step of a later start changed (D-44).
- **Results:** `measure/results_v3/summary.csv`, with the verdicts in `measure/results_v3/verdicts.md` (the rule in `measure/README.md`). Later start at 100%: 22.37 s (v2 21.32 s); first start: 87.44 s (v2 81.48 s). 64 values under the rule: 51 confirmed, 11 close, 2 missed (Q14, migraine with the index, at 50% and 100%).
- **Alternatives not taken:**
  - **An interleaved `EXTRACT_CACHE=0` / `1` pair** on the same code at 100%, A B B A A B (finding 6). Not run. v1 against v2 stays history only. Between them, the extract (`565a0a9`), the one transaction (`372b70b`), the keepalives (`6bac5f8`), the images rebuilt with constraints at 16:40 (`ffdd697`) and the schedule (no tsv-after run, a 30 s settle, `dcb6643`) all changed, and so did the machine's load. Only one gap dwarfs that noise: getting the rows, 67.43 s (`parse`) against 1.25 s (`read_extract`), which is 66.18 s of the 68.42 s gap in `full_run` (arithmetic on the two `summary.csv`). The other deltas (COPY 11.85 → 10.62 s, GIN build 1.63 → 1.31 s, the migraine query 2.76 → 1.68 ms) are not attributable to one change.
  - **An untimed warm-up start before the series** (finding 6). Not added: with the v2 protocol unchanged, v2 against v3 differs only in the code (Judgement: change one thing at a time). The round effect is predicted instead (`predictions_v3.md`, Q28).
- **The v2 round effect, by arithmetic** (`measure/results_v2/raw_runs.csv`): the first run of the benchmark (25%, round 1) was the slowest of its size. COPY took 3.56 s against 2.52 and 2.74 s, and `full_run` 12.33 s against 11.63 and 11.15 s. The first of the 3 first starts took 83.15 s against 80.97 and 80.32 s. At 50% and 100%, round 1 was not the slowest (COPY 5.27 / 5.45 / 5.06 s and 10.57 / 10.59 / 10.71 s). COPY per row is 134.7 µs at 25% without that run (runs 2-3), and 134.7 µs at 50% and 135.4 µs at 100% with all three. So the "135-151 µs" range came from that one run; the cost per row is flat.

## The atlas: tried and dropped

**D-53, No atlas.** → We tried an "atlas": a 2D map of the ingredients, placed by the words of their "Indications and usage" texts (TF-IDF, SVD, t-SNE, k-means). We removed it before the final version.
- **Why:** it is machine learning, which the project does not need and the course does not ask for; it adds three libraries (numpy, scipy, scikit-learn) and about 6 s to every start; it does not help answer our question; and we could not explain every step of it well.
- **What we kept:** the search, the Rx/OTC bars and the table of the top ingredients, and the labels of one ingredient with the matching words highlighted. The benchmark measures this version of the system.

## The FDA manifest is approximate (17 Nov)

**D-54, The manifest's size and label count: written in the log, not checked.** → The fresh-clone test of issue #8 (17 Nov 2026, new export 2026-11-17, 264,801 labels) stopped at the first zip: 130.34 MiB on disk, the manifest says 130.33, and the check allowed 0.01 MiB (D-6).
- **What we found** (`docs/evidence/v4_manifest_sizes.txt`): the 14 zips differ from the manifest's `size_mb` by -0.16 to +0.15 MiB; two downloads of the same zip from two CDN servers gave two different files (136,673,195 and 136,689,035 bytes, different ETags), both complete; the last zip holds 4,800 labels and the manifest says 4,801.
- **What changed:** `http_get` counts the bytes and compares them with the server's `Content-Length`, so a cut download is retried. The manifest's size and label count are written in the log, not checked. `same_export_or_stop` and `stale_or_redownload` are gone. Still checked: the zip opens and holds one non-empty `.json`, and a broken JSON stops the parse.
- **Price:** a cached zip from an older export is no longer found by its size; to get a newer export, delete `data/raw` and `data/clean`, as before.
- **Test:** a full load of the 17 Nov export after the change: 264,800 labels read, 84,169 kept, the page answers "migraine".
