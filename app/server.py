"""The page: the static files in app/static and three routes that run the queries in sql/queries.sql."""
import os
import time
from pathlib import Path

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row

HERE = Path(__file__).parent


def read_queries(path):
    """{'name': 'SELECT ...'} for every '-- name: name' block of the file."""
    queries = {}
    for block in path.read_text().split("-- name:")[1:]:
        name, sql = block.split("\n", 1)
        queries[name.strip()] = sql
    return queries


QUERIES = read_queries(Path(os.environ.get("QUERIES_FILE", HERE / "sql" / "queries.sql")))
app = FastAPI(docs_url=None, redoc_url=None)


def connect():
    # DATABASE_URL is for a database hosted somewhere else. Docker Compose sets the other variables.
    url = os.environ.get("DATABASE_URL")
    if url:
        return psycopg.connect(url, row_factory=dict_row)
    return psycopg.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        row_factory=dict_row,
    )


def run(db, name, params):
    """The rows of a query and how many milliseconds it took. The page shows both."""
    start = time.perf_counter()
    rows = db.execute(QUERIES[name], params).fetchall()
    return rows, round((time.perf_counter() - start) * 1000, 1)


def search_params(q, type):
    if type not in ("all", "Rx", "OTC"):
        raise HTTPException(400, "type must be all, Rx or OTC")
    return {"condition": q.strip()[:80], "product_type": type}


@app.get("/api/search")
def search(q: str = "", type: str = "all"):
    params = search_params(q, type)
    with connect() as db:
        summary, ms_summary = run(db, "condition_summary", params)
        drugs, ms_drugs = run(db, "drugs_for_condition", params)
    return {"summary": summary[0], "drugs": drugs, "ms_summary": ms_summary, "ms_drugs": ms_drugs}


@app.get("/api/labels")
def labels(drug: str, q: str = "", type: str = "all"):
    params = search_params(q, type) | {"substance_key": drug}
    with connect() as db:
        rows, ms = run(db, "labels_for_drug", params)
    return {"labels": rows, "ms_labels": ms}


@app.get("/api/info")
def info():
    with connect() as db:
        load_info = {row["key"]: row["value"] for row in db.execute("SELECT * FROM load_info")}
        timings = db.execute("SELECT step, round(seconds::numeric, 2) AS seconds, rows "
                             "FROM pipeline_timings").fetchall()
    return {"info": load_info, "timings": timings}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def page():
    return FileResponse(HERE / "static" / "index.html")


app.mount("/", StaticFiles(directory=HERE / "static"))
