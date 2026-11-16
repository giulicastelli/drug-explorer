"""Core test of the queries: the evidence in docs/evidence/core_queries_*.txt.

Runs the named queries of sql/queries.sql for three conditions, prints the top 5 of each,
EXPLAIN (ANALYZE, BUFFERS) of the main query with the index and of the variant without it.
Run it inside the app container, which has psycopg and sql/queries.sql:
    docker compose exec -T app python - < docs/evidence/run_core_queries.py
"""
import os
import time

import psycopg

DB = dict(host=os.environ.get("DB_HOST", "db"), dbname=os.environ["POSTGRES_DB"],
          user=os.environ["POSTGRES_USER"], password=os.environ["POSTGRES_PASSWORD"])


def read_named_queries(path):
    """Split sql/queries.sql on '-- name: <name>' lines (same as the loader)."""
    queries, name, lines = {}, None, []
    for line in open(path, encoding="utf-8").read().splitlines():
        if line.startswith("-- name:"):
            if name:
                queries[name] = "\n".join(lines).strip().rstrip(";")
            name, lines = line.split(":", 1)[1].strip(), []
        elif name:
            lines.append(line)
    if name:
        queries[name] = "\n".join(lines).strip().rstrip(";")
    return queries


def explain(cur, name, params):
    cur.execute("EXPLAIN (ANALYZE, BUFFERS) " + Q[name], params)
    print(f"\n== EXPLAIN (ANALYZE, BUFFERS) {name}({params['condition']!r}, {params['product_type']!r})")
    print("\n".join(r[0] for r in cur.fetchall()))


Q = read_named_queries("/app/sql/queries.sql")
MIGRAINE = {"condition": "migraine", "product_type": "all"}

with psycopg.connect(**DB) as conn, conn.cursor() as cur:
    cur.execute("SELECT version()")
    print(cur.fetchone()[0])
    cur.execute("SELECT key, value FROM load_info WHERE key IN ('sample_fraction', 'rows_loaded', 'run_id') ORDER BY key")
    print("load_info:", cur.fetchall())

    for condition in ["migraine", "epilepsy", "cancer"]:
        params = {"condition": condition, "product_type": "all"}
        cur.execute(Q["condition_summary"], params)
        print(f"\n== {condition}: condition_summary (labels, ingredients, rx, otc) =", cur.fetchone())
        t0 = time.perf_counter()
        cur.execute(Q["drugs_for_condition"], params)
        rows = cur.fetchall()
        print(f"drugs_for_condition: {len(rows)} rows in {1000 * (time.perf_counter() - t0):.1f} ms "
              "(timed from Python, first run)")
        for r in rows[:5]:
            print("  ", r)

    explain(cur, "drugs_for_condition", MIGRAINE)
    explain(cur, "drugs_for_condition", MIGRAINE)          # a second time: warm cache

    cur.execute(Q["drugs_for_condition"], {"condition": "migraine", "product_type": "OTC"})
    print("\nmigraine, OTC only, top 3:", cur.fetchall()[:3])
    cur.execute(Q["labels_for_drug"], {"condition": "migraine", "substance_key": "TOPIRAMATE"})
    rows = cur.fetchall()
    print(f"labels_for_drug('migraine', 'TOPIRAMATE'): {len(rows)} rows; first: {rows[0]}")

    t0 = time.perf_counter()
    cur.execute(Q["drugs_for_condition_on_the_fly"], MIGRAINE)
    on_the_fly = cur.fetchall()
    print(f"drugs_for_condition_on_the_fly('migraine'): {1000 * (time.perf_counter() - t0):.0f} ms "
          "(timed from Python, one run)")
    cur.execute(Q["drugs_for_condition"], MIGRAINE)
    print("same rows as drugs_for_condition:", on_the_fly == cur.fetchall())

    cur.execute("SELECT set_id, label_id FROM labels WHERE effective_date IS NULL")
    print("labels with no valid effective date:", cur.fetchall())
    cur.execute("SELECT set_id, effective_date FROM labels WHERE effective_date > now()::date")
    print("labels dated after today:", cur.fetchall())
    explain(cur, "drugs_for_condition_on_the_fly", MIGRAINE)
