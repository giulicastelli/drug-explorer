"""Download the openFDA drug labels, keep the ones we can use, load them into PostgreSQL.

Runs once and exits. The first run reads the 14 zips and saves the kept rows in
data/clean as one CSV. Later runs read that CSV, which is much faster.
"""
import csv
import hashlib
import json
import os
import time
import urllib.request
import zipfile
from datetime import date, datetime
from pathlib import Path

import ijson
import psycopg

MANIFEST_URL = "https://api.fda.gov/download.json"
LICENCE = "CC0 1.0, https://open.fda.gov/license/"

DATA = Path(os.environ.get("DATA_DIR", "/data"))
RAW = DATA / "raw"
CLEAN = DATA / "clean"
SQL = Path(__file__).parent / "sql"

SAMPLE_FRACTION = float(os.environ.get("SAMPLE_FRACTION", "1.0"))
USE_EXTRACT = os.environ.get("EXTRACT_CACHE", "1") == "1"

COLUMNS = ["set_id", "label_id", "version", "effective_date", "product_type", "substance_key",
           "generic_name", "brand_name", "manufacturer", "route", "pharm_class_epc", "bucket",
           "indications"]
BUCKET = COLUMNS.index("bucket")
PRODUCT_TYPES = {"HUMAN PRESCRIPTION DRUG": "Rx", "HUMAN OTC DRUG": "OTC"}

steps = []  # (step, seconds, rows) of this run, saved in pipeline_timings at the end


def timed(step, function, *args):
    start = time.perf_counter()
    result = function(*args)
    seconds = time.perf_counter() - start
    rows = len(result) if isinstance(result, list) else None
    steps.append((step, seconds, rows))
    print(f"{step}: {seconds:.1f} s", flush=True)
    return result


def fetch(url, dest):
    """Save url as dest. The connection to the FDA drops now and then, so try three times."""
    part = dest.with_suffix(dest.suffix + ".part")
    for attempt in (1, 2, 3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "drug-explorer"})
            with urllib.request.urlopen(request, timeout=120) as response, open(part, "wb") as out:
                expected = response.headers.get("Content-Length")  # size the FDA server announces
                received = 0
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
                    received += len(chunk)
            if expected is not None and received != int(expected):
                # a dropped connection can end the download early without an error
                raise ConnectionError(f"received {received:,} of {int(expected):,} bytes")
            part.rename(dest)  # only a complete file gets the real name
            return
        except OSError as error:
            if attempt == 3:
                raise
            print(f"{dest.name}: {error}, trying again", flush=True)
            time.sleep(5 * attempt)


def read_manifest():
    """The FDA's list of files. We keep our copy, so the zips and the list are the same export."""
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / "download.json"
    if not path.exists():
        fetch(MANIFEST_URL, path)
    manifest = json.loads(path.read_text())["results"]["drug"]["label"]
    manifest["downloaded_on"] = date.fromtimestamp(path.stat().st_mtime).isoformat()
    return manifest


def download_zips(manifest):
    paths = []
    for part in manifest["partitions"]:
        path = RAW / Path(part["file"]).name
        if not path.exists():
            print(f"downloading {path.name}, {part['size_mb']} MB", flush=True)
            fetch(part["file"], path)
        paths.append(path)
    return paths


def bucket(set_id):
    """A number from 0 to 3 that depends only on the label id.
    The 25% sample is bucket 0, the 50% sample is buckets 0 and 1."""
    return int(hashlib.md5(set_id.encode()).hexdigest()[:8], 16) % 4


def upper(text):
    return " ".join(text.upper().split())


def first(values):
    return values[0] or None if values else None


def clean(label):
    """One label from the JSON as a row for the labels table. None if we cannot use it."""
    indications = " ".join(" ".join(label.get("indications_and_usage", [])).split())
    if not indications:
        return None
    # openFDA adds this block only to the labels it could match to a known product
    fda = label.get("openfda", {})
    names = fda.get("substance_name") or fda.get("generic_name")
    if not names:
        return None
    try:
        effective = datetime.strptime(label.get("effective_time", ""), "%Y%m%d").date()
    except ValueError:
        effective = None
    version = label.get("version") or ""
    product_type = first(fda.get("product_type")) or ""
    generic = first(fda.get("generic_name"))
    return [
        label["set_id"],
        label["id"],
        int(version) if version.isdigit() else None,
        effective,
        PRODUCT_TYPES.get(product_type, product_type.title() or "Unknown"),
        " + ".join(sorted({upper(name) for name in names})),
        upper(generic) if generic else None,
        first(fda.get("brand_name")),
        first(fda.get("manufacturer_name")),
        "; ".join(fda.get("route", [])) or None,
        "; ".join(fda.get("pharm_class_epc", [])) or None,
        bucket(label["set_id"]),
        indications,
    ]


def parse(zips):
    """Read the labels one at a time, straight from the zips.
    Each zip holds one JSON file of 600 to 700 MB, too big to load whole."""
    kept = {}
    for path in zips:
        with zipfile.ZipFile(path) as archive, archive.open(archive.namelist()[0]) as file:
            for label in ijson.items(file, "results.item"):
                row = clean(label)
                if row is None:
                    continue
                # a few labels come twice, keep the newer version
                old = kept.get(row[0])
                if old is None or (row[2] or 0) > (old[2] or 0):
                    kept[row[0]] = row
        print(f"{path.name}: {len(kept):,} labels kept so far", flush=True)
    return list(kept.values())


def write_extract(rows, path):
    CLEAN.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(COLUMNS)
        writer.writerows(rows)


def read_extract(path):
    with open(path, newline="", encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader)
        # the csv module writes None as an empty field, turn it back
        return [[value or None for value in row] for row in reader]


def load(rows, manifest, started):
    with psycopg.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    ) as db:
        # Everything below is one transaction. If the loader stops half-way,
        # the database keeps the tables of the run before.
        db.execute("DROP TABLE IF EXISTS labels, drugs, load_info, pipeline_timings")
        db.execute((SQL / "schema.sql").read_text())

        def copy():
            with db.cursor().copy(f"COPY labels ({', '.join(COLUMNS)}) FROM STDIN") as out:
                for row in rows:
                    out.write_row(row)

        timed("copy", copy)
        # the index after the rows: building it once is faster than updating it 84,000 times
        timed("index_build", db.execute, (SQL / "indexes.sql").read_text())
        timed("build_drugs", db.execute, (SQL / "drugs.sql").read_text())
        timed("analyze", db.execute, "ANALYZE")

        info = {
            "source_url": MANIFEST_URL,
            "licence": LICENCE,
            "export_date": manifest["export_date"],
            "downloaded_on": manifest["downloaded_on"],
            "labels_in_export": manifest["total_records"],
            "sample_fraction": SAMPLE_FRACTION,
            "rows_loaded": len(rows),
        }
        db.cursor().executemany("INSERT INTO load_info VALUES (%s, %s)",
                                [(key, str(value)) for key, value in info.items()])
        steps.append(("pipeline_total", time.perf_counter() - started, len(rows)))
        db.cursor().executemany("INSERT INTO pipeline_timings VALUES (%s, %s, %s)", steps)


def main():
    if SAMPLE_FRACTION not in (0.25, 0.5, 0.75, 1.0):
        raise SystemExit("SAMPLE_FRACTION must be 0.25, 0.5, 0.75 or 1.0")
    manifest = read_manifest()
    extract = CLEAN / f"labels_{manifest['export_date']}.csv"

    if USE_EXTRACT and extract.exists():
        started = time.perf_counter()
        rows = timed("read_extract", read_extract, extract)
    else:
        zips = timed("download", download_zips, manifest)
        started = time.perf_counter()  # the download depends on the network, we time the rest
        rows = timed("parse", parse, zips)
        if USE_EXTRACT:
            timed("write_extract", write_extract, rows, extract)

    rows = [row for row in rows if int(row[BUCKET]) < SAMPLE_FRACTION * 4]
    load(rows, manifest, started)
    print(f"loaded {len(rows):,} of the {manifest['total_records']:,} labels in the export", flush=True)


if __name__ == "__main__":
    main()
