"""Query benchmark: the main query with the GIN index, without it, and on the fly.

Runs inside the loader image, after a normal load (the index exists):
    docker compose run --rm --no-deps -e RUN_ID=bench-0.25-r1 loader python bench_queries.py

Three ways to answer drugs_for_condition, for 5 fixed conditions:
  with_index     tsv @@ query, the GIN index finds the labels           1 warm-up + 3 timed
  without_index  the same query after DROP INDEX: every stored tsv read  1 warm-up + 3 timed
  on_the_fly     to_tsvector(indications) @@ query: every label stemmed  1 warm-up + 1 timed
                 again (no index can serve it). Only 1 timed run: it takes seconds, not ms.
The drill-down labels_for_drug (migraine, its top ingredient) is timed with and without the index.
The index is built again (timed), then the disk sizes and the row counts are read.
with_index / without_index run in the order BENCH_ORDER gives (benchmark.py alternates it).

Everything goes into pipeline_timings, like the loader's own steps:
  - time steps (query_*, index_build_bench):  seconds = measured time, rows = rows returned
  - disk steps (disk_*):                      seconds = 0, rows = size in BYTES
  - counts (count_*) and checks (check_*):    seconds = 0, rows = the number (check: 1 = yes, 0 = no)
EXPLAIN (ANALYZE, BUFFERS) plans are printed between BEGIN/END EXPLAIN markers;
measure/benchmark.py saves them to files.
"""
import os
import time
from datetime import datetime, timezone

# Reuse the loader's connection (with retries) and its reader of sql/queries.sql.
# Importing load_fda does not run its main(): it is guarded by __name__.
from load_fda import SQL_DIR, connect, read_named_queries

RUN_ID = os.environ.get("RUN_ID", "bench-queries")
CONDITIONS = ["migraine", "hypertension", "epilepsy", "asthma", "cancer"]   # fixed: the same every run
DRILL_CONDITION = "migraine"
# with_first | without_first: measure/benchmark.py alternates it between runs, so one index state
# is not always measured first.
ORDER = os.environ.get("BENCH_ORDER", "with_first")
REPS = {"with_index": 3, "without_index": 3, "on_the_fly": 1}
results = []     # (step, seconds, rows, detail, started_at, finished_at), written at the end
answers = {}     # (mode, condition) -> rows of drugs_for_condition; (mode, 'summary', condition) -> counts


def log(msg):
    print(f"[bench {RUN_ID}] {msg}", flush=True)


def now():
    return datetime.now(timezone.utc)


def record(step, seconds, rows=None, detail=None, started=None):
    finished = now()
    results.append((step, seconds, rows, detail, started or finished, finished))
    log(f"{step}: {seconds:.4f} s, rows={rows} {detail or ''}")


def run(cur, sql, params):
    """Execute and fetch every row, as the dashboard would. Returns (seconds, rows, start time)."""
    started = now()
    t0 = time.perf_counter()
    cur.execute(sql, params)
    rows = cur.fetchall()
    return time.perf_counter() - t0, rows, started


def explain(cur, sql, params, name):
    cur.execute("EXPLAIN (ANALYZE, BUFFERS) " + sql, params)
    print(f"----- BEGIN EXPLAIN {name} -----", flush=True)
    print("\n".join(r[0] for r in cur.fetchall()), flush=True)
    print("----- END EXPLAIN -----", flush=True)


def bench_conditions(cur, queries, mode):
    """drugs_for_condition for every condition: 1 warm-up (not timed, fills the cache) + REPS timed."""
    sql = queries["drugs_for_condition_on_the_fly" if mode == "on_the_fly" else "drugs_for_condition"]
    for condition in CONDITIONS:
        params = {"condition": condition, "product_type": "all"}
        _, answers[(mode, condition)], _ = run(cur, sql, params)          # warm-up
        for rep in range(1, REPS[mode] + 1):
            seconds, rows, started = run(cur, sql, params)
            record(f"query_drugs_for_condition_{mode}_{condition}_rep{rep}", seconds, len(rows), None, started)
    explain(cur, sql, {"condition": DRILL_CONDITION, "product_type": "all"}, f"drugs_for_condition {mode}")


def bench_index_state(cur, queries, mode, drug):
    """One index state (with_index | without_index): the main query, the headline counts, the drill-down."""
    bench_conditions(cur, queries, mode)
    for condition in CONDITIONS:
        # The headline numbers (labels, ingredients), so the answer can be checked to stay the same.
        cur.execute(queries["condition_summary"], {"condition": condition, "product_type": "all"})
        answers[(mode, "summary", condition)] = cur.fetchone()
        n_labels, n_ingredients, n_rx, n_otc = answers[(mode, "summary", condition)]
        record(f"count_labels_{condition}_{mode}", 0.0, n_labels, f"rx={n_rx} otc={n_otc}")
        record(f"count_ingredients_{condition}_{mode}", 0.0, n_ingredients)
    params = {"condition": DRILL_CONDITION, "substance_key": drug, "product_type": "all"}
    run(cur, queries["labels_for_drug"], params)                           # warm-up
    for rep in range(1, REPS[mode] + 1):
        seconds, rows, started = run(cur, queries["labels_for_drug"], params)
        record(f"query_labels_for_drug_{mode}_rep{rep}", seconds, len(rows), f"{DRILL_CONDITION} / {drug}", started)
    explain(cur, queries["labels_for_drug"], params, f"labels_for_drug {mode}")


def main():
    queries = read_named_queries(SQL_DIR / "queries.sql")
    index_sql = (SQL_DIR / "indexes.sql").read_text(encoding="utf-8")
    with connect() as conn, conn.cursor() as cur:
        conn.autocommit = True                       # every DROP / CREATE takes effect at once
        # No automatic prepared statements: psycopg prepares a query after 5 runs, and PostgreSQL
        # may then switch to a generic plan. Each timed run is planned like one dashboard call.
        conn.prepare_threshold = None

        # The drill-down ingredient, chosen the same way every run: the top answer for migraine.
        seconds, rows, started = run(cur, queries["drugs_for_condition"],
                                     {"condition": DRILL_CONDITION, "product_type": "all"})
        drug = rows[0][0]
        record("pick_drill_drug", seconds, rows[0][1], drug, started)

        record("bench_order", 0.0, None, ORDER)
        if ORDER == "with_first":
            bench_index_state(cur, queries, "with_index", drug)
        cur.execute("DROP INDEX labels_tsv_gin")
        try:
            bench_index_state(cur, queries, "without_index", drug)
            # On the fly: the GIN index could not serve it anyway; run while it is dropped.
            bench_conditions(cur, queries, "on_the_fly")
        finally:
            # Put the index back, even after an error, so the dashboard stays fast.
            # Timed: the cost of an index is also its build time.
            started, t0 = now(), time.perf_counter()
            cur.execute(index_sql)
            record("index_build_bench", time.perf_counter() - t0, None, None, started)
        if ORDER == "without_first":
            bench_index_state(cur, queries, "with_index", drug)

        # The same answer in the three modes? (an index must change the speed, never the result)
        for condition in CONDITIONS:
            same = (answers[("with_index", condition)] == answers[("without_index", condition)]
                    == answers[("on_the_fly", condition)]
                    and answers[("with_index", "summary", condition)] == answers[("without_index", "summary", condition)])
            record(f"check_same_answer_{condition}", 0.0, int(same),
                   f"{len(answers[('with_index', condition)])} rows of drugs_for_condition in the 3 modes; "
                   "condition_summary with and without the index")

        # Disk. Bytes in rows.
        # pg_relation_size(t) = the main heap file only. Long values (indications, big tsv) are
        # compressed and moved to the TOAST table, which pg_total_relation_size counts:
        # total - heap - indexes = TOAST (its table and its index) + the heap's free space and visibility maps.
        for step, expr in [
                ("disk_database_bytes", "pg_database_size(current_database())"),
                ("disk_labels_table_bytes", "pg_relation_size('labels')"),
                ("disk_labels_gin_index_bytes", "pg_relation_size('labels_tsv_gin')"),
                ("disk_labels_indexes_bytes", "pg_indexes_size('labels')"),          # GIN + primary key
                ("disk_labels_total_bytes", "pg_total_relation_size('labels')"),
                ("disk_labels_toast_bytes", "pg_total_relation_size('labels') - pg_relation_size('labels')"
                                            " - pg_indexes_size('labels')"),
                ("disk_labels_toast_only_bytes", "(SELECT pg_total_relation_size(reltoastrelid) FROM pg_class"
                                                 " WHERE oid = 'labels'::regclass)"),
                ("disk_drugs_total_bytes", "pg_total_relation_size('drugs')"),
                # What the two big columns take as stored (after compression), summed over the rows.
                ("disk_indications_column_bytes", "(SELECT sum(pg_column_size(indications)) FROM labels)"),
                ("disk_tsv_column_bytes", "(SELECT sum(pg_column_size(tsv)) FROM labels)")]:
            cur.execute(f"SELECT {expr}")
            record(step, 0.0, cur.fetchone()[0], "bytes (in the rows column)")
        for table in ("labels", "drugs"):
            cur.execute(f"SELECT count(*) FROM {table}")
            record(f"count_rows_{table}", 0.0, cur.fetchone()[0])

        cur.executemany("INSERT INTO pipeline_timings (run_id, step, seconds, rows, detail, started_at, finished_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)", [(RUN_ID, *r) for r in results])
    log(f"{len(results)} results written to pipeline_timings")


if __name__ == "__main__":
    main()
