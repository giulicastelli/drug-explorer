"""Loader: download the openFDA drug label export, keep the labels that can answer
"which drugs treat this condition?", load them into PostgreSQL, build the full-text
index and the drugs table.

One-shot container. Every step is timed with time.perf_counter() and the timings
are written to the table pipeline_timings, so the benchmark and the dashboard read
them from the database.

Safe to run again (idempotent): the tables are emptied with TRUNCATE before
loading, and downloaded files are reused from /data/raw. TRUNCATE, COPY, the index, the
drugs table, ANALYZE and load_info are one transaction: a run that dies half-way leaves
the previous complete load.
Extract cache: the first start parses the zips and writes every usable row once to
/data/clean/labels_<export_date>_<clean_version>.csv; later starts read that file instead of
the zips. clean_version changes with the cleaning code, so changed rules mean a new parse.
Fails loudly: any error stops the run with a message and exit code 1, so docker
compose does not start the dashboard on a half-loaded database.
"""
import csv
import hashlib
import http.client
import inspect
import json
import os
import random
import resource
import ssl
import sys
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import ijson
import psycopg

# ---------------------------------------------------------------- settings
# All settings come from the environment (.env + docker-compose.yml).
DB = dict(
    host=os.environ.get("DB_HOST", "db"),          # the service name, never localhost
    port=int(os.environ.get("DB_PORT", "5432")),
    dbname=os.environ["POSTGRES_DB"],
    user=os.environ["POSTGRES_USER"],
    password=os.environ["POSTGRES_PASSWORD"],
)
SAMPLE_FRACTION = float(os.environ.get("SAMPLE_FRACTION", "1.0"))
CREATE_INDEX = os.environ.get("CREATE_INDEX", "1") == "1"
# generated: the stored tsv column is computed by PostgreSQL during COPY (default).
# after: COPY without the column, then add it in one pass over the table (measured: D-9).
# expression: measurement mode only (measure/gin_expression.sh): no stored column at all; the GIN
#   index is built on the expression to_tsvector('english', indications), so only a query that
#   repeats that exact expression can use it. The dashboard's queries name tsv: never start the app.
TSV_MODE = os.environ.get("TSV_MODE", "generated")
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data")) / "raw"
CLEAN_DIR = DATA_DIR.parent / "clean"              # the extract: the usable rows of one export
# 1: read the extract when it exists for this export (and write it after a parse).
# 0: always parse the zips and write nothing (for the measurements).
EXTRACT_CACHE = os.environ.get("EXTRACT_CACHE", "1") == "1"
SQL_DIR = Path(os.environ.get("SQL_DIR", Path(__file__).parent / "sql"))
RUN_ID = os.environ.get("RUN_ID") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:6]

# openFDA bulk download. The manifest lists the 14 zip files of the drug label export.
# Licence: CC0 1.0 Universal, https://open.fda.gov/license/
MANIFEST_URL = "https://api.fda.gov/download.json"
LICENCE = "CC0 1.0 Universal (public domain dedication), https://open.fda.gov/license/"
PRODUCT_TYPES = {"HUMAN PRESCRIPTION DRUG": "Rx", "HUMAN OTC DRUG": "OTC"}
COLUMNS = ("set_id", "label_id", "version", "effective_date", "product_type", "substance_key",
           "generic_name", "brand_name", "manufacturer", "route", "pharm_class_epc", "bucket",
           "indications")


def log(msg):
    print(f"[loader {RUN_ID}] {msg}", flush=True)


def buckets_for(fraction):
    """25% / 50% / 100% of the labels = hash buckets {0} / {0,1} / {0,1,2,3}.
    The same label always falls in the same bucket, so the samples are nested and reproducible."""
    n = fraction * 4
    if n not in (1, 2, 3, 4):
        raise ValueError(f"SAMPLE_FRACTION must be 0.25, 0.5, 0.75 or 1.0, got {fraction}")
    return set(range(int(n)))


def bucket(set_id):
    """md5 of the set id, first 8 hex digits as a number, modulo 4: a uniform, fixed split."""
    return int(hashlib.md5(set_id.encode()).hexdigest()[:8], 16) % 4


# ---------------------------------------------------------------- download
def http_get(url, dest, attempts=6, timeout=120):
    """Download url to dest. Timeouts, retries with backoff and jitter.
    Writes to a .part file and renames it, so a broken download never looks finished."""
    part = dest.with_name(dest.name + ".part")
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "cids-drug-explorer-loader/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp, open(part, "wb") as out:
                expected = resp.headers.get("Content-Length")   # the size the server says it is sending
                received = 0
                while chunk := resp.read(1 << 20):     # 1 MiB at a time: never the whole file in memory
                    out.write(chunk)
                    received += len(chunk)
            if expected is not None and received != int(expected):
                # A connection that closes early can end the read without an error: count the bytes.
                raise ConnectionError(f"received {received:,} of {int(expected):,} bytes")
            part.rename(dest)
            return
        # URLError: DNS, refused, HTTP errors. TimeoutError: no answer within `timeout`.
        # ConnectionError: includes ConnectionResetError. HTTPException: a body cut short
        # (IncompleteRead). SSLError: a TLS failure in the middle of the read.
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException, ssl.SSLError) as exc:
            # 4xx (not 429, "too many requests"): the server answered that this URL is wrong or forbidden;
            # asking again gives the same answer, so stop at once instead of a minute of retries.
            if isinstance(exc, urllib.error.HTTPError) and 400 <= exc.code < 500 and exc.code != 429:
                raise RuntimeError(f"download refused, HTTP {exc.code}, not retried: {url}") from exc
            if attempt == attempts:
                raise RuntimeError(f"download failed after {attempts} attempts: {url}\n  last error: {exc}") from exc
            wait = min(60, 2 ** attempt) + random.uniform(0, 1)
            log(f"download error ({exc}); retry {attempt}/{attempts - 1} in {wait:.1f} s")
            time.sleep(wait)


def check_zip(path, partition):
    """A zip is readable only if its directory, at the very end of the file, is there: a
    download cut short fails here, not in the middle of the parse. Returns the JSON size."""
    try:
        with zipfile.ZipFile(path) as z:
            members = z.infolist()
    except zipfile.BadZipFile as exc:
        raise RuntimeError(f"{path.name}: not a readable zip ({exc}). Delete it and run again.") from exc
    if len(members) != 1 or not members[0].filename.endswith(".json") or members[0].file_size == 0:
        raise RuntimeError(f"{path.name}: expected one non-empty .json file inside, found "
                           f"{[(m.filename, m.file_size) for m in members]}. Delete it and run again.")
    return members[0].file_size


def size_ok(path, partition):
    """Does the file match the manifest's size_mb (MiB, 2 decimals)? Only written in the log: in the
    export of 17 Nov 2026 the manifest differs from the real files by up to 0.16 MiB, and two copies
    of the same file, served by different CDN servers, differ by 15 KB. A cut download is caught by
    http_get (byte count), a broken zip by check_zip, a wrong file by the label count in parse."""
    return abs(path.stat().st_size / 2 ** 20 - float(partition["size_mb"])) <= 0.01


def download():
    """Fetch the manifest, then every partition not yet in data/raw, unless the extract of this
    export (and of these clean rules) exists: then the zips are not needed and not checked.
    The cached manifest is reused with the cached files: they belong to the same export.
    To get a newer export, delete data/raw and data/clean."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = DATA_DIR / "download.json"
    downloaded = 0
    if manifest_path.exists() and manifest_path.stat().st_size > 0:
        log("download.json: already downloaded, reused")
    else:
        log(f"download.json: downloading {MANIFEST_URL}")
        try:
            http_get(MANIFEST_URL, manifest_path)
        except RuntimeError as exc:
            # Judgement: an extract is there, but without the manifest the loader cannot tell
            # whether it is still the current export (data/raw, with the cached manifest, is
            # gone). Loading it anyway would be a guess, so stop and say why.
            found = sorted(p.name for p in CLEAN_DIR.glob("labels_*.csv"))
            if found:
                raise RuntimeError(f"{exc}\n  data/clean holds {', '.join(found)}, but without the manifest "
                                   "the loader cannot tell which export is current, and it does not guess. "
                                   "Run again when api.fda.gov answers.") from exc
            raise
        downloaded += 1
    export = json.loads(manifest_path.read_text(encoding="utf-8"))["results"]["drug"]["label"]
    partitions = export["partitions"]
    log(f"export_date {export['export_date']}: {len(partitions)} files, {export['total_records']:,} labels")
    if EXTRACT_CACHE and extract_path(export).exists():
        # The extract holds every usable row of this export, so the 1.86 GB of zips may even be
        # deleted. The price: a later start no longer re-verifies the zips (they are not read).
        log(f"{extract_path(export).name} exists: the zips are not needed, not checked")
        return export, [], downloaded, 0

    files, json_bytes = [], 0
    for p in partitions:
        dest = DATA_DIR / Path(p["file"]).name
        if dest.exists() and dest.stat().st_size > 0:
            log(f"{dest.name}: already downloaded, reused")
        else:
            log(f"{dest.name}: downloading {p['size_mb']} MiB")
            http_get(p["file"], dest)
            downloaded += 1
        if not size_ok(dest, p):
            log(f"{dest.name}: {dest.stat().st_size / 2 ** 20:.2f} MiB on disk, the manifest says {p['size_mb']} "
                "(the manifest's size is approximate: the zip and its label count are checked instead)")
        json_bytes += check_zip(dest, p)
        files.append((dest, int(p["records"])))
    return export, files, downloaded, json_bytes


# ---------------------------------------------------------------- parse and clean
def norm(text):
    """'Ibuprofen  sodium ' -> 'IBUPROFEN SODIUM'."""
    return " ".join(text.upper().split())


def first(of, key):
    """The first value of an openfda list field, or None: of["brand_name"] = ["Advil", ...].
    An empty string is None too, so no row holds "" (the extract relies on it)."""
    return (of.get(key) or [None])[0] or None


def clean(r, counts):
    """One label (a dict) -> one row for the labels table, or None with the reason counted.
    Every bucket is kept here: the sample is applied after (rows that go into the extract)."""
    indications = " ".join(" ".join(r.get("indications_and_usage") or []).split())
    if not indications:
        counts["dropped_no_indications"] += 1
        return None
    of = r.get("openfda") or {}           # the harmonised names: present on about 31% of labels
    names = sorted({norm(x) for x in of.get("substance_name", [])})
    if not names:                         # no substance name: fall back to the generic name
        names = sorted({norm(x) for x in of.get("generic_name", [])})
        if names:
            counts["name_from_generic_name"] += 1
    if not names:
        counts["dropped_no_name"] += 1
        return None
    try:
        effective = datetime.strptime(r.get("effective_time", ""), "%Y%m%d").date()
    except ValueError:
        effective = None
        counts["bad_effective_time"] += 1
    version = r.get("version")
    product_type = (of.get("product_type") or [""])[0]
    return (
        r["set_id"],
        r["id"],
        int(version) if version and version.isdigit() else None,
        effective,
        PRODUCT_TYPES.get(product_type, product_type.title() or "Unknown"),
        " + ".join(names),
        norm(first(of, "generic_name")) if first(of, "generic_name") else None,
        first(of, "brand_name"),
        first(of, "manufacturer_name"),
        "; ".join(of.get("route", [])) or None,
        "; ".join(of.get("pharm_class_epc", [])) or None,
        bucket(r["set_id"]),
        indications,
    )


def parse(files):
    """Stream every zip with ijson: one label at a time, straight from the compressed file,
    never unzipped to disk and never the whole 600-700 MB of JSON in memory.
    Every partition is read whatever SAMPLE_FRACTION is: the bucket of a label is known only
    after reading it. The usable rows of all 4 buckets stay in memory (a list of tuples), so
    they can be written to the extract; the sample is taken after."""
    counts = dict(read=0, kept=0, dropped_no_indications=0, dropped_no_name=0,
                  duplicate_set_id=0, name_from_generic_name=0, bad_effective_time=0, manifest_records=0)
    rows, position = [], {}               # position: set_id -> index in rows
    for path, expected in files:
        t0, n = time.perf_counter(), 0
        with zipfile.ZipFile(path) as z, z.open(z.infolist()[0]) as f:
            for r in ijson.items(f, "results.item"):
                n += 1
                row = clean(r, counts)
                if row is None:
                    continue
                if row[0] in position:    # the export has one row per set_id; keep the newest version
                    counts["duplicate_set_id"] += 1
                    i = position[row[0]]
                    if (row[2] or 0) > (rows[i][2] or 0):
                        rows[i] = row
                    continue
                position[row[0]] = len(rows)
                rows.append(row)
        counts["read"] += n
        counts["manifest_records"] += expected
        if n != expected:
            # Noted, not an error: in the export of 17 Nov 2026 the last file holds 4,800 labels and the
            # manifest says 4,801. A damaged file fails earlier: a broken zip or JSON stops the read.
            log(f"{path.name}: {n:,} labels read, the manifest says {expected:,} (noted, the load goes on)")
        log(f"{path.name}: {n:,} labels in {time.perf_counter() - t0:.1f} s; usable rows so far {len(rows):,}")
    counts["kept"] = len(rows)
    return rows, counts


# ---------------------------------------------------------------- extract (data/clean)
# The extract holds the OUTPUT of the rules above, so its name carries the export date AND a
# version of those rules: 8 hex digits of the md5 of the source of the functions that decide
# the rows (norm, first, bucket, clean, parse: names, drops, dedup of set_id) plus the columns
# and the product types. A changed rule gives a new name, and the next start parses the zips
# again instead of loading old rows. Why a hash and not a constant bumped by hand: the bump is
# exactly the step that gets forgotten (review round 2). The price: a comment edited inside
# these functions also costs one parse (59.07 s at 100%, measure/results_v2/summary.csv).
ROW_RULES = (norm, first, bucket, clean, parse)
CLEAN_VERSION = hashlib.md5(("".join(inspect.getsource(f) for f in ROW_RULES)
                             + repr((COLUMNS, PRODUCT_TYPES))).encode()).hexdigest()[:8]


def extract_path(export):
    return CLEAN_DIR / f"labels_{export['export_date']}_{CLEAN_VERSION}.csv"


# CSV with a header. QUOTE_NOTNULL quotes every value except NULL, so an unquoted empty
# field is NULL: the same rule as PostgreSQL's COPY ... (FORMAT csv), so the file can also be
# loaded by hand with \copy. Python 3.12's reader cannot tell "" from an empty field, so
# read_extract turns every empty field into None; clean() never writes "" (see first()).
def write_extract(rows, path):
    """All usable rows, once, to path. Written to a .part file and renamed, so an
    interrupted write never looks finished (same rule as the downloads)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    with open(part, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_NOTNULL)
        w.writerow(COLUMNS)
        w.writerows(rows)
    part.rename(path)
    return path.stat().st_size


def read_extract(path, keep_buckets):
    """The rows of the sample from the extract. Values stay text (COPY sends text anyway,
    PostgreSQL parses the numbers and dates); empty = NULL. Only the kept rows stay in memory."""
    rows, n = [], 0
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f, quoting=csv.QUOTE_NOTNULL)
        if tuple(next(r)) != COLUMNS:
            raise RuntimeError(f"{path.name}: unexpected header. Delete data/clean and run again.")
        b = COLUMNS.index("bucket")
        for row in r:
            n += 1
            if int(row[b]) in keep_buckets:
                rows.append(tuple(v if v else None for v in row))
    return rows, n


# ---------------------------------------------------------------- database
def connect(attempts=10):
    """The healthcheck already waits for the database; retrying here as well
    costs nothing and survives a database that restarts.
    Server-side TCP keepalives for this session only: if the loader dies (docker kill) the
    server may never see the connection close, and its open transaction would keep the
    TRUNCATE lock (every reader waits) for the OS default of 2 hours. With 10 s idle and
    3 probes 5 s apart, PostgreSQL drops it and rolls back after about 25 s
    (docs/evidence/v2_atomic.txt)."""
    keepalive = "-c tcp_keepalives_idle=10 -c tcp_keepalives_interval=5 -c tcp_keepalives_count=3"
    for attempt in range(1, attempts + 1):
        try:
            return psycopg.connect(**DB, connect_timeout=5, options=keepalive)
        except psycopg.OperationalError as exc:
            if attempt == attempts:
                raise
            wait = min(30, 2 ** attempt) * 0.5 + random.uniform(0, 0.5)
            log(f"database not reachable ({exc.__class__.__name__}); retry in {wait:.1f} s")
            time.sleep(wait)


def read_named_queries(path):
    """Split sql/queries.sql on '-- name: <name>' lines."""
    queries, name, lines = {}, None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("-- name:"):
            if name:
                queries[name] = "\n".join(lines).strip().rstrip(";")
            name, lines = line.split(":", 1)[1].strip(), []
        elif name:
            lines.append(line)
    if name:
        queries[name] = "\n".join(lines).strip().rstrip(";")
    return queries


TSV_COLUMN = "tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', indications)) STORED"
# TSV_MODE=expression: the same words, but only in the index (same name, so DROP INDEX above finds it).
EXPRESSION_INDEX = "CREATE INDEX labels_tsv_gin ON labels USING gin (to_tsvector('english', indications))"


# ---------------------------------------------------------------- main
def main():
    t_start = time.perf_counter()
    keep = buckets_for(SAMPLE_FRACTION)
    if TSV_MODE not in ("generated", "after", "expression"):
        raise ValueError(f"TSV_MODE must be generated, after or expression, got {TSV_MODE!r}")
    log(f"settings: sample_fraction={SAMPLE_FRACTION} buckets={sorted(keep)} create_index={CREATE_INDEX} "
        f"tsv_mode={TSV_MODE} clean_version={CLEAN_VERSION} data_dir={DATA_DIR} db_host={DB['host']} ijson_backend={ijson.backend}")
    timings = []   # [step, seconds, rows, detail, started_at, finished_at]

    def timed(step, fn, *args):
        started = datetime.now(timezone.utc)
        t0 = time.perf_counter()
        result = fn(*args)
        seconds = time.perf_counter() - t0
        timings.append([step, seconds, None, None, started, datetime.now(timezone.utc)])
        log(f"{step}: {seconds:.2f} s")
        return result

    export, files, n_downloaded, json_bytes = timed("download", download)
    zip_bytes = sum(p.stat().st_size for p, _ in files)
    timings[-1][3] = (f"files downloaded now: {n_downloaded}; reused: {len(files) + 1 - n_downloaded}; "
                      f"zip_bytes={zip_bytes} json_bytes={json_bytes}"
                      + ("; zips not checked (the extract exists)" if not files else ""))
    t_pipeline = time.perf_counter()     # the pipeline proper starts here: download is reported apart

    extract = extract_path(export)
    if not files:                  # download() found the extract and skipped the zips
        # Later starts: the usable rows of this export come from the extract, not the zips.
        rows, n_all = timed("read_extract", read_extract, extract, keep)
        step, counts = timings[-1], {"rows_in_extract": n_all}
        load_path = f"read_extract {extract.name}"
    else:
        # The parse reads all 14 files at every sample size: it does not shrink with the sample.
        rows, counts = timed("parse", parse, files)
        step, n_all = timings[-1], len(rows)
        if EXTRACT_CACHE:          # first start: keep the result of the parse for the next ones
            size = timed("write_extract", write_extract, rows, extract)
            timings[-1][2:4] = [n_all, f"{extract.name} bytes={size}"]
            load_path = f"parse, extract written {extract.name}"
            others = sorted(p.name for p in CLEAN_DIR.glob("labels_*.csv") if p != extract)
            if others:            # never deleted by the loader: that is the user's choice
                log(f"data/clean also holds {', '.join(others)} (another export or other clean rules): "
                    "not used; delete to free the disk")
        else:
            load_path = "parse (EXTRACT_CACHE=0: extract not read, not written)"
        rows = [row for row in rows if row[11] in keep]      # the sample: the buckets of set_id
    counts["kept"], counts["outside_sample"] = len(rows), n_all - len(rows)
    # Peak memory of the whole run so far: after a parse, all 4 buckets were in memory at once.
    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024   # Linux: kilobytes
    step[2] = len(rows)
    step[3] = (" ".join(f"{k}={v}" for k, v in counts.items())
               + f" loader_peak_rss_mb={peak_mb:.0f} path={load_path}")
    log(f"{step[0]} counts: " + step[3])

    with connect() as conn, conn.cursor() as cur:
        queries = read_named_queries(SQL_DIR / "queries.sql")

        def schema():
            cur.execute((SQL_DIR / "schema.sql").read_text(encoding="utf-8"))
            # Idempotency: empty the tables instead of appending a second copy. The index is
            # dropped too, so COPY does not update it row by row (it is rebuilt after).
            cur.execute("DROP INDEX IF EXISTS labels_tsv_gin")
            cur.execute("TRUNCATE labels, drugs")
            cur.execute("SELECT 1 FROM information_schema.columns "
                        "WHERE table_schema = current_schema() AND table_name = 'labels' AND column_name = 'tsv'")
            has_tsv = cur.fetchone() is not None
            if TSV_MODE in ("after", "expression"):
                # Measurement modes only. PostgreSQL keeps a dropped column in its catalog,
                # so use them on a fresh volume (docker compose down -v).
                cur.execute("ALTER TABLE labels DROP COLUMN IF EXISTS tsv")
            elif not has_tsv:
                # Self-healing: CREATE TABLE IF NOT EXISTS does not change an existing table, so a
                # volume made by an older schema.sql (or a column dropped by hand) has no tsv, and
                # the index build would fail. The table is empty here (TRUNCATE above), so adding
                # it back costs nothing; COPY then fills it. Other schema changes: down -v.
                log("labels has no tsv column (a volume from an older schema.sql?): adding it back before COPY")
                cur.execute(f"ALTER TABLE labels ADD COLUMN {TSV_COLUMN}")
        timed("schema_and_truncate", schema)

        def copy_rows():
            # One stream, one round trip per buffer.
            # In generated mode PostgreSQL computes tsv for every row while it writes it.
            with cur.copy(f"COPY labels ({', '.join(COLUMNS)}) FROM STDIN") as copy:
                for row in rows:
                    copy.write_row(row)
            return len(rows)
        timed("copy", copy_rows)
        timings[-1][2] = len(rows)
        timings[-1][3] = f"tsv_mode={TSV_MODE}"

        if TSV_MODE == "after":
            # One pass over the finished table: PostgreSQL rewrites it with the new column filled.
            timed("tsv_fill", cur.execute, f"ALTER TABLE labels ADD COLUMN {TSV_COLUMN}")
            timings[-1][2] = len(rows)

        # Still the same transaction: no COMMIT between TRUNCATE and the end of load_info.
        # A crash anywhere before the one commit below rolls everything back, so the database
        # keeps the previous complete load (or stays empty): never labels without their index
        # or an empty drugs table. ANALYZE is allowed in a transaction (VACUUM is not).
        if CREATE_INDEX:
            timed("index_build", cur.execute, EXPRESSION_INDEX if TSV_MODE == "expression"
                  else (SQL_DIR / "indexes.sql").read_text(encoding="utf-8"))
            cur.execute("SELECT pg_relation_size('labels_tsv_gin')")
            timings[-1][3] = f"index_bytes={cur.fetchone()[0]}"

        def build_drugs():
            cur.execute(f"INSERT INTO drugs {queries['drugs']}")
            return cur.rowcount
        n_drugs = timed("build_drugs", build_drugs)
        timings[-1][2] = n_drugs

        timed("analyze", cur.execute, "ANALYZE labels, drugs")

        cur.execute("SELECT min(effective_date), max(effective_date), pg_total_relation_size('labels') FROM labels")
        first_date, last_date, labels_bytes = cur.fetchone()
        zips = [DATA_DIR / Path(p["file"]).name for p in export["partitions"]]
        if all(z.exists() for z in zips):     # also when they were not read (the extract was)
            downloaded_on = min(datetime.fromtimestamp(z.stat().st_mtime, timezone.utc) for z in zips).date().isoformat()
        else:   # zips deleted: the extract was written from them, just after their download
            downloaded_on = (datetime.fromtimestamp(extract.stat().st_mtime, timezone.utc).date().isoformat()
                             + " (date the extract was written; the zips are no longer on disk)")
        info = {
            "source": "openFDA drug label bulk export (FDA Structured Product Labeling), "
                      f"{len(export['partitions'])} zip files listed in the manifest",
            "source_url": MANIFEST_URL,
            "licence": LICENCE,
            "export_date": export["export_date"],
            "downloaded_on": downloaded_on,
            "labels_in_export": str(export["total_records"]),
            "sample_fraction": str(SAMPLE_FRACTION),
            "buckets": ",".join(map(str, sorted(keep))),
            "rows_loaded": str(len(rows)),
            "drugs": str(n_drugs),
            "effective_date_first": str(first_date),
            "effective_date_last": str(last_date),
            "labels_bytes_with_indexes": str(labels_bytes),   # heap + TOAST + primary key + GIN
            "tsv_mode": TSV_MODE,
            "create_index": str(int(CREATE_INDEX)),
            "run_id": RUN_ID,
            "load_path": load_path,                    # parse of the zips, or read of the extract
        } | {f"parse_{k}": str(v) for k, v in counts.items()}
        cur.execute("DELETE FROM load_info")         # load_info describes this load only
        cur.executemany("INSERT INTO load_info VALUES (%s, %s)", list(info.items()))
        timed("commit", conn.commit)                 # the one commit: the new load appears at once

        # The step log, in a second small transaction: losing it in a crash loses no data.
        pipeline_seconds = time.perf_counter() - t_pipeline
        now = datetime.now(timezone.utc)
        started_pipeline = timings[1][4]
        timings.append(["pipeline_total", pipeline_seconds, len(rows), "everything after the download",
                        started_pipeline, now])
        timings.append(["total_with_download", time.perf_counter() - t_start, len(rows), None, timings[0][4], now])
        cur.executemany("INSERT INTO pipeline_timings (run_id, step, seconds, rows, detail, started_at, finished_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)", [(RUN_ID, *t) for t in timings])
        conn.commit()

        # The answer, as a plain table in the log (the checkpoint asks for "even a plain table").
        # (expression mode: there is no tsv; the on-the-fly text repeats the indexed expression)
        cur.execute(queries["drugs_for_condition_on_the_fly" if TSV_MODE == "expression" else "drugs_for_condition"],
                    {"condition": "migraine", "product_type": "all"})
        log("ANSWER for 'migraine' (labels, Rx/OTC): " + "; ".join(
            f"{r[0]} {r[1]} ({r[2]}/{r[3]})" for r in cur.fetchall()[:5]))
        log(f"rows loaded: {len(rows):,}; drugs: {n_drugs:,}; effective dates {first_date} to {last_date}; "
            f"pipeline {pipeline_seconds:.1f} s (download excluded)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # fail loudly: a clear message and a non-zero exit code
        print(f"[loader] FAILED: {exc.__class__.__name__}: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
