# How to run: the details

The README keeps the six steps and three commands. This file has the rest, moved out of the README after README test round 3 (problem 2: "The README is not one screen"). Run every command in the `drug-explorer` folder. Stop a running stack first (`Ctrl-C`, or `docker compose down` after `-d`).

## How long it takes, and where each time comes from

- **First start, cold** (fresh-clone test on the cloud VM: clone of `60c3342`, the v3 code, empty `data/`): `docker compose build --no-cache` 67.9 s, then `docker compose up --build` to the first HTTP 200 on `/` 98.6 s, which includes the download of the 14 zips (1,858,907,416 bytes, 14.84 s on that network) and their parse (60.03 s). About 3 minutes in all: 166.5 s (arithmetic, 67.9 + 98.6; two commands, so not one measured number), plus the `postgres:16` pull, not timed because the image was already there. Round 2, on the v2 code `b5ecc7c`: 74.0 + 97.8 = 171.8 s. The research download of the same zips took 85.7 s (`docs/environment.md`): the network decides that part.
- **Later start** (`docker compose up`): the loader reads the extract in `data/clean/` and reloads the database. Benchmark v3: 22.37 s at 100% (`measure/results_v3/summary.csv`). README test round 3: 24.3 s to the first HTTP 200 with the zips on disk, 23.5 s after `rm data/raw/*.zip`, 26.0 s after `rm -rf data/raw`.
- **Start without reloading** (`docker compose up -d --wait --no-deps db app`): uses the database already in the volume. `--wait` returns when the app's healthcheck passes (`app/Dockerfile:13-14`, `/_stcore/health` every 5 s): 6.28 s, and 6.23 s with the containers reused after a stop, HTTP 200 right after both. Without `--wait` the page answered after 2.08 s in round 3 and 1.57 s in round 2, but nothing tells you when: `docker compose logs -f app`, which the v3 README advised, prints the ready line of every earlier run once the container is reused (5 copies in round 3). Judgement: `--wait` costs about 4 s because the first healthcheck runs 5 s after the start.
- **Stop:** `Ctrl-C` took 3.3 s in round 3.

## Disk

Images 1.69 GB, `data/` 1.93 GB, database 0.14 GB; the build cache was not measured. Since v3 the zips are not needed after the first start: `rm data/raw/*.zip` (Linux after the `chown`: `sudo rm`) frees 1.86 GB. Keep `data/raw/download.json` and a later start needs no network (`docs/evidence/v3_extract_without_zips.txt`); without it the loader fetches only that 0.6 MB manifest (round 3: 0.50 s). An offline start was not tested.

## The extract key

The file is `labels_<export date>_<clean_version>.csv`; `clean_version` is 8 hex digits of an md5 of the loader's row rules (`norm`, `first`, `bucket`, `clean`, `parse`, the columns). A new export or a changed rule gives a new name, so the loader parses the zips again, downloading them if they are gone (`docs/evidence/v3_extract_key.txt`). Old extracts are named in the log ("not used; delete to free the disk"), never deleted. `rm -rf data/clean` frees that disk; do it too after changing what the hash does not cover (`write_extract`, `read_extract`, library versions; read from the code).

## Other options

- **Quicker sample:** `SAMPLE_FRACTION=0.25 docker compose up --build` (PowerShell: `$env:SAMPLE_FRACTION="0.25"; docker compose up --build`).
- **Check the count:** `docker compose exec db sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT count(*) FROM labels"'` prints 78472 (19546 at 25%).
- **Port 8501 busy:** `APP_PORT=8502 docker compose up --build`, then http://localhost:8502 (the log still prints 8501, the port inside the container).
- **Delete:** `docker compose down -v` deletes the database (volume `dbdata`); it is needed after changing `sql/schema.sql`. For a newer openFDA export: `rm -rf data/raw data/clean` (Linux after the `chown`: `sudo rm -rf …`).

## Linux, step 4 skipped

Tested by the README tester of round 2: the loader prints `PermissionError: [Errno 13] Permission denied: '/data/raw'` and exits 1, the app never starts, and `db` is left running. Recover (not run as a test): `docker compose down`, then step 4, then step 5 (`docs/evidence/v3_app_waits_for_loader.txt`).
