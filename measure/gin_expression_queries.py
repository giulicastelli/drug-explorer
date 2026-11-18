"""GIN expression-index experiment, the query side (one load = one call of this script).

The question (one we had not answered in the schema notes): why a stored
GENERATED tsv column plus a GIN index on it, and not a GIN index on the expression
to_tsvector('english', indications) with no stored column?
measure/gin_expression.sh loads the data in one of the two states, then runs this script:
    TSV_MODE=generated   the v2 schema: column tsv stored in every row, GIN index on tsv
    TSV_MODE=expression  no tsv column; GIN index ON labels USING gin (to_tsvector('english', indications))
The queries are those of sql/queries.sql. In expression mode "tsv @@" is replaced by the
indexed expression, exactly as written in the index, so the planner can match the two.

Runs inside the loader image, with measure/ mounted:
    docker compose run --rm --no-deps -v ./measure:/measure -e TSV_MODE=... loader \
        python /measure/gin_expression_queries.py
Prints CSV lines starting with "ROW," (step, value, unit, detail) and the plans between
BEGIN/END EXPLAIN markers.
"""
import os
import sys
import time

sys.path.insert(0, "/app")                       # the loader's code inside the image
from load_fda import SQL_DIR, connect, read_named_queries  # noqa: E402

MODE = os.environ["TSV_MODE"]
EXPRESSION = "to_tsvector('english', indications)"   # character for character as in the index
REPS = 3
# migraine: one word. type 2 diabetes: a phrase; GIN stores no word positions, so for a phrase
# every candidate row is checked again on the heap (the "recheck"), where the words must be
# read from tsv (generated) or computed again from indications (expression).
CONDITIONS = ["migraine", "type 2 diabetes"]


def row(step, value, unit, detail=""):
    print(f"ROW,{step},{value},{unit},{detail}", flush=True)


def query_text(queries, name):
    sql = queries[name]
    if MODE == "expression":
        assert sql.count("tsv @@") == 1, name
        sql = sql.replace("tsv @@", f"{EXPRESSION} @@")
    return sql


def main():
    queries = read_named_queries(SQL_DIR / "queries.sql")
    q1, q2 = query_text(queries, "drugs_for_condition"), query_text(queries, "condition_summary")
    with connect() as conn, conn.cursor() as cur:
        conn.autocommit = True
        conn.prepare_threshold = None            # each run planned like one dashboard call
        cur.execute("SELECT pg_get_indexdef('labels_tsv_gin'::regclass)")
        row("index_definition", 0, "text", cur.fetchone()[0].replace(",", ";"))

        # Disk, in bytes. heap = the main file of labels; TOAST = its toast table and toast index
        # (long values, compressed); then the two indexes and the whole database.
        for step, expr in [
                ("disk_heap_bytes", "pg_relation_size('labels')"),
                ("disk_toast_bytes", "(SELECT pg_total_relation_size(reltoastrelid) FROM pg_class WHERE oid = 'labels'::regclass)"),
                ("disk_gin_index_bytes", "pg_relation_size('labels_tsv_gin')"),
                ("disk_pkey_bytes", "pg_relation_size('labels_pkey')"),
                ("disk_labels_total_bytes", "pg_total_relation_size('labels')"),
                ("disk_database_bytes", "pg_database_size(current_database())")]:
            cur.execute(f"SELECT {expr}")
            row(step, cur.fetchone()[0], "bytes")
        if MODE == "generated":
            cur.execute("SELECT sum(pg_column_size(tsv)) FROM labels")
            row("disk_tsv_column_bytes", cur.fetchone()[0], "bytes", "sum of pg_column_size(tsv) over the rows")
        cur.execute("SELECT count(*) FROM labels")
        row("count_rows_labels", cur.fetchone()[0], "rows")

        for condition in CONDITIONS:
            params = {"condition": condition, "product_type": "all"}
            tag = condition.replace(" ", "_")
            cur.execute(q2, params)                       # the headline: must not change with the mode
            n_labels, n_ingredients, n_rx, n_otc = cur.fetchone()
            row(f"answer_{tag}", n_labels, "labels", f"ingredients={n_ingredients} rx={n_rx} otc={n_otc}")
            cur.execute(q1, params)
            top = cur.fetchall()                          # warm-up, not timed
            row(f"answer_top_{tag}", len(top), "rows", f"first={top[0][0]} ({top[0][1]} labels)")
            for rep in range(1, REPS + 1):
                t0 = time.perf_counter()
                cur.execute(q1, params)
                cur.fetchall()
                row(f"query_drugs_for_condition_{tag}", round((time.perf_counter() - t0) * 1000, 3), "ms", f"rep{rep}")
            cur.execute("EXPLAIN (ANALYZE, BUFFERS) " + q1, params)
            plan = [r[0] for r in cur.fetchall()]
            print(f"----- BEGIN EXPLAIN drugs_for_condition {condition} ({MODE}) -----", flush=True)
            print("\n".join(plan), flush=True)
            print("----- END EXPLAIN -----", flush=True)
            row(f"explain_execution_ms_{tag}", plan[-1].split(":")[1].strip().split()[0], "ms", "EXPLAIN ANALYZE")
            removed = [line.strip() for line in plan if "Rows Removed by Index Recheck" in line]
            row(f"explain_rows_removed_by_recheck_{tag}", removed[0].split(":")[1].strip() if removed else 0, "rows")


if __name__ == "__main__":
    main()
