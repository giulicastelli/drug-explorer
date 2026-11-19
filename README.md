# Drug explorer

Which drugs treat this condition? Type "migraine" and the page lists the active ingredients
whose FDA label names migraine under "Indications and usage", with the number of labels for
each one, prescription (Rx) or over the counter (OTC).

Group D, Computing Infrastructures for Data Science, LUISS 2026/27.

A public copy of the page is at https://drug-explorer-xi.vercel.app. It is the same page and the
same queries, with the page on Vercel and the database on Neon. The project is the three
containers described below.

## Team

Alessandro D'Amore, Andrea D'Ascanio, Federico Davolos, Giulia Castelli, Giovanni Margiacchi

## How to run

You need Docker Desktop (Mac or Windows) or Docker Engine with Compose (Linux), running, about
5 GB of free disk and port 8080 free.

```
git clone https://github.com/giulicastelli/drug-explorer
cd drug-explorer
cp .env.example .env
docker compose up
```

On Linux only, if `id -u` does not print 1000, run `sudo chown 1000 data` before
`docker compose up`: the containers do not run as root, and the loader writes the downloaded
files in `data`.

When the log prints `Application startup complete`, open http://localhost:8080.

The first start downloads 1.87 GB into `data/raw`, so give it a few minutes. After that the
files stay there and a start takes about 13 seconds. If you only want a quick look, load a
quarter of the labels with `SAMPLE_FRACTION=0.25 docker compose up`.

`docker compose down` stops everything and keeps the database. Add `-v` to delete it.

Tested from a clean clone on: [TO FILL IN AFTER THE TESTS: laptop and who].

## Data

The labels come from openFDA, the FDA's open data site: 14 zip files listed in
https://api.fda.gov/download.json. The loader downloads them itself. There is no key and no
login. The licence is CC0 (https://open.fda.gov/license/), so the data is public domain, and it
holds no personal data: these are the leaflets that companies file with the FDA.

We used the export of 13 Nov 2026, downloaded on 16 Nov. It has 264,748 labels. We keep 84,381
of them, the ones with a standard ingredient name and an indications text. The rest cannot
answer our question. The FDA publishes a new export every week, so a clone run on another day
can give slightly different counts. The page shows which export it loaded.

[docs/dataset_decision.md](docs/dataset_decision.md) says why we picked this dataset and what
it cannot tell.

## Architecture

![Architecture](docs/architecture.png)

`docker compose up` starts three containers.

`db` is PostgreSQL 16. Its files are in a Docker volume, so the data is still there after a
restart. The other two containers wait until it accepts connections.

`loader` is a Python script that runs once and exits. It downloads the zips, reads the labels
one at a time (each zip holds a JSON file of more than 600 MB), keeps the usable ones and loads
them. It also saves the kept rows as one CSV in `data/clean`, so the next start does not have
to read the zips again.

`app` is the page: a small FastAPI server and plain HTML, CSS and JavaScript. Compose starts it
only when the loader has finished, and it is the only container with a port open to the laptop.

Both images we build run as a normal user, not as root, and install the exact library versions
listed in `constraints.txt`, so a build next month gets the same libraries.

We chose PostgreSQL. The raw labels are nested JSON, and at first that made us think of
MongoDB. But we keep 13 fields per label, the same for all of them, and what we do with them
is count labels per ingredient. That is a table and a `GROUP BY`. PostgreSQL also has
full-text search built in, which is what the question needs.
[docs/schema.md](docs/schema.md) has the tables.

The processing happens in two places. The loader cleans the labels and builds the ingredient
key ("ACETAMINOPHEN + ASPIRIN + CAFFEINE"). PostgreSQL stores the stemmed words of every
indications text and indexes them. A search is then one SQL query that finds the labels with
those words, counts them per ingredient and returns the first 25. The queries are in
[sql/queries.sql](sql/queries.sql).

On the page you get a search box with suggestions, four totals, the ranked ingredients with a
bar each, and for the ingredient you select the sentences of its labels that matched.

Labels also say what a drug is not for. ADHD drugs came up under "psychosis", because their
labels say they are "not intended for" children with psychosis. So before indexing we cut the
words from "not indicated", "not recommended", "not approved", "not intended", "not used" or
"not for use" to the end of the sentence. This changes 6,604 of the 84,381 labels. "Psychosis"
went from 64 labels to 2, and 65 of the 81 conditions the page suggests did not change at all.

One warning. This is still a word search. "Cancer" finds sunscreens first, because their labels
say "decreases the risk of skin cancer". Do not use it as medical advice.

Our choices, and what we tried and dropped along the way, are in
[docs/decision_log.md](docs/decision_log.md).

## Measurements

Measured on a MacBook Pro with an Apple M2 Pro and 32 GB of RAM. Docker Desktop had 12 CPUs and
7.75 GiB. Each number is the mean of 3 runs, and every run starts from an empty database.
`python3 measure/rerun/benchmark.py` runs them all again. The single values are in
[measure/rerun/results/runs.csv](measure/rerun/results/runs.csv).

| | 25% | 50% | 100% |
|---|---|---|---|
| Labels loaded | 21,107 | 42,107 | 84,576 |
| Load, first start | 35.9 s | 37.6 s | 41.2 s |
| Load, later start | 3.0 s | 5.0 s | 8.4 s |
| `docker compose up` until the page answers, first start | 40.8 s | 42.4 s | 46.1 s |
| `docker compose up` until the page answers, later start | 7.9 s | 10.0 s | 13.2 s |
| "migraine" query, with the index | 0.9 ms | 0.8 ms | 0.7 ms |
| "migraine" query, without the index | 8.2 ms | 19.4 ms | 33.8 ms |
| Peak memory, loader | 200 MiB | 218 MiB | 283 MiB |
| Peak memory, db | 61 MiB | 76 MiB | 121 MiB |
| Peak memory, app | 41 MiB | 41 MiB | 41 MiB |
| Database on disk | 44 MB | 78 MB | 147 MB |

The runs are of 18 Nov 2026 and loaded the export of that day, which has 264,929 labels and
84,576 that we keep. That is 195 more than in the export of 13 Nov described above.

"First start" means the loader reads the zips. "Later start" means it reads the saved CSV. The
zips were already on disk, so the download is not in these times. Memory is the highest value
`docker stats` showed, asked about once a second.

What we read in these numbers.

Loading grows more slowly than the data. With 4 times the labels a later start loads in 2.8
times the time (3.0 s to 8.4 s), because part of every load does not depend on the size: reading
the saved CSV takes 0.8 s whatever the sample.

The first start costs the same at every size. Reading the 14 zips takes about 33 s whether we
keep a quarter of the labels or all of them, since the loader has to look at every label to
decide. That is why it saves the kept rows: at 100% the start goes from 46.1 s to 13.2 s.

The index is what makes the search fast. With it "migraine" answers in under a millisecond at
every size. Without it the time doubles when the data doubles, and at 100% it is 49 times
slower. The index takes 12 MB and 0.8 s to build.

It fits on a normal laptop. The loader never goes over 283 MiB, although each zip holds more
than 600 MB of JSON, because it reads one label at a time. The database is 147 MB, 7.9% of the
1.87 GB of zips.

The memory of `db` is the least steady number: at 100% the three runs gave between 106 and 151
MiB. We ask `docker stats` once a second, so a short peak can be missed.

## What we changed, and why

This is the second version of the project. The first one answered the same question with a
Streamlit page and a loader of 549 lines. It worked, and we measured it three times. When we
went through it for the presentation we found problems, so on 18 and 19 Nov we rebuilt it.

What was wrong:

- Some results were wrong. ADHD drugs came up under "psychosis", because the search also read
  the sentences that say what a drug is not for.
- The loader had grown to 549 lines, with checks that not all of us could explain. Any of us
  can be asked about any part, so that was a problem too.
- The page was a Streamlit app. We wanted one we could read line by line and put online.

What we did:

- The search leaves out the "not indicated" sentences. "Psychosis" went from 64 labels to 2.
- The loader is 232 lines and does the same job: download, keep the usable labels, load them
  in one transaction, save the kept rows for the next start.
- The page is a small FastAPI server and plain HTML. It runs the same three queries, suggests
  81 conditions and symptoms while you type, and it is also online.
- We did it in three pull requests, one for each owner: the schema (Andrea, #53), the loader and
  the page (Alessandro, #52), Compose, README and slides (Giulia, #54).

What it cost. The measurements of the first version no longer describe the code, and its
benchmark does not run on the new loader. We kept them as the record of the first version, in
[measure/README.md](measure/README.md), and measured the new one again (`measure/rerun`).

What is still wrong. "Cancer" still finds sunscreens. We tried a stricter rule, a treatment
word within 8 words of the condition, and dropped it. The page says this limit openly.

## Who did what

| Who | Part |
|---|---|
| Alessandro D'Amore | Getting the data and loading it, the rewrite of the loader and of the page |
| Andrea D'Ascanio | The database: tables, index, queries, the decision log |
| Federico Davolos | The page: the first Streamlit version, testing the new page |
| Giulia Castelli | Docker, the README, the diagram, the tests from a clean clone |
| Giovanni Margiacchi | Measurements |
