"""Times the main query with and without the index. benchmark.py runs it inside the app container."""
import json
import time

from server import QUERIES, connect

REPEATS = 3


def mean_ms(db, condition):
    params = {"condition": condition, "product_type": "all"}
    db.execute(QUERIES["drugs_for_condition"], params).fetchall()  # once to warm up
    start = time.perf_counter()
    for _ in range(REPEATS):
        db.execute(QUERIES["drugs_for_condition"], params).fetchall()
    return round((time.perf_counter() - start) * 1000 / REPEATS, 2)


out = {}
with connect() as db:
    for condition in ("migraine", "type 2 diabetes"):
        name = condition.replace(" ", "_")
        out[f"query_ms_index_{name}"] = mean_ms(db, condition)
        # drop the index only inside a transaction, so the rollback puts it back
        db.commit()
        db.execute("DROP INDEX labels_tsv_gin")
        out[f"query_ms_no_index_{name}"] = mean_ms(db, condition)
        db.rollback()

    summary = db.execute(QUERIES["condition_summary"],
                         {"condition": "migraine", "product_type": "all"}).fetchone()
    out["migraine_labels"] = summary["n_labels"]
    out["migraine_ingredients"] = summary["n_ingredients"]
    out["labels"] = db.execute("SELECT count(*) AS n FROM labels").fetchone()["n"]
    out["db_bytes"] = db.execute("SELECT pg_database_size(current_database()) AS n").fetchone()["n"]
    out["index_bytes"] = db.execute("SELECT pg_relation_size('labels_tsv_gin') AS n").fetchone()["n"]

print(json.dumps(out))
