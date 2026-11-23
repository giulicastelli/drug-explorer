# How to run: the details

The README has the four commands. This file has the rest. Run every command in the
`drug-explorer` folder.

This file describes the version of 19 Nov 2026. The details of the first version (the
Streamlit page on port 8501, the tests of the README on the cloud machine) are in this file as
it was at commit `d9082a8`.

## How long it takes

Times from `measure/rerun/results`, on a MacBook Pro with an Apple M2 Pro, at 100% of the labels.

- **First start.** The loader downloads the 14 zips (1.87 GB) into `data/raw`. How long that
  takes depends on the network, and we did not measure it. Then it reads them: 46.1 s from
  `docker compose up` until the page answers.
- **Later start.** The loader reads the saved CSV in `data/clean` and loads the database again:
  13.2 s.

The images are built on the first `docker compose up`. We did not time the build.

## Options

- **A smaller sample:** `SAMPLE_FRACTION=0.25 docker compose up` loads a quarter of the labels,
  `0.5` loads half. PowerShell: `$env:SAMPLE_FRACTION="0.25"; docker compose up`.
- **Port 8080 busy:** `APP_PORT=8081 docker compose up`, then http://localhost:8081.
- **Read the zips again:** `EXTRACT_CACHE=0 docker compose up` does not use the saved CSV.
- **After an older version:** `git pull`, then `docker compose up --build`. Without
  `--build` Docker starts the images of the last build, which can be the old page.
- **Check the count:**
  `docker compose exec db sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT count(*) FROM labels"'`
  prints the number the page shows at the bottom.
- **Stop:** `Ctrl-C`, or `docker compose down`. The database stays in the volume `dbdata`.
  `docker compose down -v` deletes it. The next start loads it again anyway.
- **A newer export:** the loader keeps the FDA's file list (`data/raw/download.json`) next to
  the zips, so it stays on the export it downloaded first. To get the newest one, delete
  `data/raw` and `data/clean` and start again.

## Disk

`data/raw` holds 1.87 GB of zips and `data/clean` one CSV of about 79 MB. The database is
147 MB at 100%. `data/` is never committed.

## Linux

The containers do not run as root. They run as user 1000, and the loader writes in `data`. If
`id -u` does not print 1000, run `sudo chown 1000 data` before the first start. Without it the
loader stops with `PermissionError: [Errno 13] Permission denied: '/data/raw'`, and the page
never starts.
