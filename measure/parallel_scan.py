"""Parallel-scan experiment: why the migraine query WITHOUT the index ran as a plain Seq Scan
with no worker, while the on-the-fly query used 2 workers (measure/results/explain/100pct_*.txt).

The planner's estimate of a sequential scan is, per PostgreSQL's cost model,
    disk part  relpages  x seq_page_cost                                     (not shared by workers)
    CPU part   reltuples x (cpu_tuple_cost + cost of the filter per row)     (shared by the workers)
and a parallel plan adds parallel_setup_cost once plus parallel_tuple_cost per row sent up.
This script prints every one of those inputs (SHOW, pg_class, pg_proc), then the plans:
  1. EXPLAIN (estimates only) of the migraine query without the index, with the default settings
     and with each parallel setting at 0, one at a time and all three together;
  2. the same for the on-the-fly query, as it runs and with workers forbidden;
  3. timed runs: default (D) and SET parallel_setup_cost = 0, parallel_tuple_cost = 0,
     min_parallel_table_scan_size = 0 (P), rounds in the order D P P D D P, each round
     1 warm-up + 3 timed from Python (what a client waits) and 1 EXPLAIN (ANALYZE, BUFFERS)
     (what the database spends);
  4. the index built again, and the same 3 rounds with it, for the speed-up of the index
     seen inside the database and from Python.
Run after a normal load at 100%, inside the loader image (measure/parallel_scan.sh does it).
Prints "ROW," lines (step, value, unit, detail) and plans between BEGIN/END EXPLAIN markers.
"""
import sys
import time

sys.path.insert(0, "/app")                       # the loader's code inside the image
from load_fda import SQL_DIR, connect, read_named_queries  # noqa: E402

REPS = 3
PARAMS = {"condition": "migraine", "product_type": "all"}
PARALLEL = {"parallel_setup_cost": "0", "parallel_tuple_cost": "0", "min_parallel_table_scan_size": "0"}
SETTINGS = ["max_parallel_workers_per_gather", "max_parallel_workers", "max_worker_processes",
            "parallel_setup_cost", "parallel_tuple_cost", "min_parallel_table_scan_size",
            "parallel_leader_participation", "seq_page_cost", "random_page_cost", "cpu_tuple_cost",
            "cpu_operator_cost", "shared_buffers", "work_mem", "effective_cache_size", "jit", "server_version"]


def row(step, value, unit, detail=""):
    print(f"ROW,{step},{value},{unit},{detail}", flush=True)


def settings(cur, values):
    cur.execute("RESET ALL")
    for name, value in values.items():
        cur.execute(f"SET {name} = {value}")


def plan(cur, sql, name, analyze=False):
    """EXPLAIN; prints the plan; returns its lines."""
    cur.execute(("EXPLAIN (ANALYZE, BUFFERS) " if analyze else "EXPLAIN ") + sql, PARAMS)
    lines = [r[0] for r in cur.fetchall()]
    print(f"----- BEGIN EXPLAIN {name} -----\n" + "\n".join(lines) + "\n----- END EXPLAIN -----", flush=True)
    return lines


def estimate(lines, name):
    """The top node's estimated total cost, the scan node and the workers planned."""
    top = lines[0].split("cost=")[1].split("..")[1].split()[0]
    scan = next(line.strip() for line in lines if "Seq Scan on labels" in line)
    workers = next((line.split(":")[1].strip() for line in lines if "Workers Planned" in line), "0")
    row(f"estimate_{name}", top, "cost units", f"workers planned={workers}; scan node: {scan.split('  (')[0]} "
        f"cost={scan.split('cost=')[1].split()[0]} rows={scan.split('rows=')[1].split()[0]}")


def timed(cur, sql, name):
    cur.execute(sql, PARAMS)
    cur.fetchall()                                   # warm-up, not timed
    for rep in range(1, REPS + 1):
        t0 = time.perf_counter()
        cur.execute(sql, PARAMS)
        cur.fetchall()
        row(f"client_ms_{name}", round((time.perf_counter() - t0) * 1000, 3), "ms", f"rep{rep}")


def rounds(cur, sql, order, label):
    for n, mode in enumerate(order, 1):
        settings(cur, PARALLEL if mode == "P" else {})
        name = f"{label}_{'parallel_settings' if mode == 'P' else 'default'}"
        timed(cur, sql, name)
        lines = plan(cur, sql, f"{name} round {n}", analyze=True) if n <= 2 else None
        if lines is None:                            # rounds 3-6: the time only, not the whole plan again
            cur.execute("EXPLAIN (ANALYZE, BUFFERS) " + sql, PARAMS)
            lines = [r[0] for r in cur.fetchall()]
        launched = next((line.split(":")[1].strip() for line in lines if "Workers Launched" in line), "0")
        row(f"db_ms_{name}", lines[-1].split(":")[1].strip().split()[0], "ms",
            f"round {n}; EXPLAIN ANALYZE Execution Time; workers launched={launched}")


def main():
    queries = read_named_queries(SQL_DIR / "queries.sql")
    q_stored, q_fly = queries["drugs_for_condition"], queries["drugs_for_condition_on_the_fly"]
    with connect() as conn, conn.cursor() as cur:
        conn.autocommit = True
        conn.prepare_threshold = None                # each run planned like one dashboard call
        for name in SETTINGS:
            cur.execute(f"SHOW {name}")
            row(f"setting_{name}", cur.fetchone()[0], "setting")
        # What the planner knows about the table (filled by the loader's ANALYZE), and the real sizes.
        cur.execute("""SELECT c.relpages, c.reltuples, pg_relation_size(c.oid), t.relpages, t.reltuples,
                              pg_relation_size(t.oid)
                       FROM pg_class c JOIN pg_class t ON t.oid = c.reltoastrelid WHERE c.oid = 'labels'::regclass""")
        for step, value in zip(["labels_relpages", "labels_reltuples", "labels_heap_bytes",
                                "toast_relpages", "toast_reltuples", "toast_bytes"], cur.fetchone()):
            row(step, value, "pg_class" if "rel" in step else "bytes")
        # The cost of the filter per row: procost x cpu_operator_cost (the @@ operator, the stemmer).
        cur.execute("""SELECT oid::regprocedure, procost FROM pg_proc
                       WHERE oid IN ('ts_match_vq(tsvector,tsquery)'::regprocedure,
                                     'to_tsvector(regconfig,text)'::regprocedure)""")
        for fn, procost in cur.fetchall():
            row("procost", procost, "x cpu_operator_cost", str(fn).replace(",", ";"))

        cur.execute("DROP INDEX labels_tsv_gin")     # put back in step 4
        # 1. Without the index: what the planner estimates, setting by setting.
        for name, values in [("default", {}),
                             ("parallel_setup_cost_0", {"parallel_setup_cost": "0"}),
                             ("parallel_tuple_cost_0", {"parallel_tuple_cost": "0"}),
                             ("min_parallel_table_scan_size_0", {"min_parallel_table_scan_size": "0"}),
                             ("setup_and_tuple_cost_0", {"parallel_setup_cost": "0", "parallel_tuple_cost": "0"}),
                             ("all_three_0", PARALLEL)]:
            settings(cur, values)
            estimate(plan(cur, q_stored, f"estimate without_index {name}"), f"without_index_{name}")
        # 2. On the fly: as it runs (parallel), and the serial plan the planner rejected.
        for name, values in [("default", {}), ("no_workers", {"max_parallel_workers_per_gather": "0"})]:
            settings(cur, values)
            estimate(plan(cur, q_fly, f"estimate on_the_fly {name}"), f"on_the_fly_{name}")
        # 3. Timed, without the index: default against the three parallel settings at 0.
        rounds(cur, q_stored, "DPPDDP", "without_index")
        # 4. The index again (as after a load), then the indexed query the same way (default settings).
        settings(cur, {})
        t0 = time.perf_counter()
        cur.execute((SQL_DIR / "indexes.sql").read_text(encoding="utf-8"))
        row("index_rebuild", round(time.perf_counter() - t0, 3), "s")
        cur.execute("ANALYZE labels")
        rounds(cur, q_stored, "DDD", "with_index")


if __name__ == "__main__":
    main()
