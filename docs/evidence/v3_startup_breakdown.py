"""Where the seconds of a later start go (docs/evidence/v3_startup_breakdown.txt).

One run = the benchmark's later start (measure/benchmark.py one_run, mode generated, 100%):
down -v, OS cache dropped, 30 s settle, then `docker compose up -d`, with the extract in data/clean.
Three clocks, all from this host's kernel, so they line up:
  - docker events: create / start / health_status / die of each container (daemon time, ns);
  - the loader's own step log: pipeline_timings.started_at / finished_at, and the time Docker
    stamped on its first log line (docker logs -t);
  - this script: when `up -d` was called, and the first HTTP 200 on /_stcore/health and on /,
    polled every 0.05 s (the benchmark polls every 0.5 s and calls `docker compose ps` in between).
Run from the repo root as root (for the cache drop):  python3 docs/evidence/v3_startup_breakdown.py 3
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

PROJECT, PORT, SETTLE_S = "de-v3", 8581, 30
COMPOSE = ["docker", "compose", "-p", PROJECT]
ENV = dict(os.environ, APP_PORT=str(PORT), SAMPLE_FRACTION="1.0")


def sh(*args, **kw):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kw).stdout


def ts(iso):
    """'2026-11-05T19:57:04.996562463Z' or '2026-11-05 19:57:04.99+00' -> epoch seconds."""
    iso = iso.replace(" ", "T").replace("Z", "+00:00")
    if iso.endswith("+00"):
        iso += ":00"
    head, _, frac = iso.partition(".")
    if frac:                                   # Python 3.11+ parses at most 6 decimals
        digits = "".join(c for c in frac if c.isdigit())
        iso = f"{head}.{digits[:6]}{frac[len(digits):]}"
    return datetime.fromisoformat(iso).timestamp()


def status(path):
    try:
        with urllib.request.urlopen(f"http://localhost:{PORT}{path}", timeout=2) as r:
            return r.status
    except OSError:
        return None


def one_run(n):
    run_id = f"v3-startup-{n}"
    sh(*COMPOSE, "down", "-v", "--remove-orphans", env=ENV)
    sh("sync")
    Path("/proc/sys/vm/drop_caches").write_text("3\n")
    time.sleep(SETTLE_S)
    since = str(time.time())
    events = subprocess.Popen(["docker", "events", "--since", since, "--filter", f"label=com.docker.compose.project={PROJECT}",
                               "--filter", "type=container", "--format", "{{json .}}"], stdout=subprocess.PIPE, text=True)
    t0 = time.time()
    sh(*COMPOSE, "up", "-d", env=dict(ENV, RUN_ID=run_id))
    t_up_returned = time.time()
    first = {}
    while len(first) < 2 and time.time() - t0 < 300:
        for path in ("/_stcore/health", "/"):
            if path not in first and status(path) == 200:
                first[path] = time.time()
        time.sleep(0.05)
    time.sleep(1)
    events.terminate()
    marks = {}                                 # (service, action) -> epoch seconds, first occurrence
    for line in events.stdout:
        e = json.loads(line)
        action = e["Action"]
        if action.startswith("exec_"):         # the healthcheck's own pg_isready runs
            continue
        service = e["Actor"]["Attributes"].get("com.docker.compose.service")
        marks.setdefault((service, action), e["timeNano"] / 1e9)
    steps = sh(*COMPOSE, "exec", "-T", "db", "psql", "-U", "team", "-d", "drugs", "-AtF", "|", "-c",
               f"SELECT step, started_at, finished_at, seconds FROM pipeline_timings WHERE run_id = '{run_id}' "
               "ORDER BY started_at, finished_at", env=ENV).split("\n")
    steps = {s: (ts(a), ts(b), float(sec)) for s, a, b, sec in (x.split("|") for x in steps if x)}
    first_log = ts(sh("docker", "logs", "-t", f"{PROJECT}-loader-1").split()[0])
    return dict(t0=t0, up_returned=t_up_returned, marks=marks, steps=steps, first_log=first_log,
                health=first.get("/_stcore/health"), page=first.get("/"))


def phases(r):
    """(label, from, to) in time order, each phase starting where the one before ends, so the rows
    add up to the total: every second from `up -d` to the first 200 on /."""
    m, s = r["marks"], r["steps"]
    healthy = m[("db", "health_status: healthy")]
    return [
        ("up -d called -> db container created", r["t0"], m[("db", "create")]),
        ("db created -> db started (all 3 containers are created first)", m[("db", "create")], m[("db", "start")]),
        ("db started -> db healthy (initdb on the new volume; pg_isready every 3 s)", m[("db", "start")], healthy),
        ("db healthy -> loader started (compose sees service_healthy)", healthy, m[("loader", "start")]),
        ("loader started -> first log line (Python start, imports)", m[("loader", "start")], r["first_log"]),
        ("download step (manifest reused; zips not checked)", r["first_log"], s["download"][1]),
        ("read_extract", s["download"][1], s["read_extract"][1]),
        ("connect to db + schema_and_truncate", s["read_extract"][1], s["schema_and_truncate"][1]),
        ("copy", s["schema_and_truncate"][1], s["copy"][1]),
        ("index_build", s["copy"][1], s["index_build"][1]),
        ("build_drugs", s["index_build"][1], s["build_drugs"][1]),
        ("analyze", s["build_drugs"][1], s["analyze"][1]),
        ("load_info rows + commit", s["analyze"][1], s["commit"][1]),
        ("commit -> loader container died (step log, the migraine answer, exit)", s["commit"][1], m[("loader", "die")]),
        ("loader died -> app started (service_completed_successfully)", m[("loader", "die")], m[("app", "start")]),
        ("app started -> first 200 on /_stcore/health (Streamlit start)", m[("app", "start")], r["health"]),
        ("first 200 on /_stcore/health -> first 200 on /", r["health"], r["page"]),
    ]


def main():
    runs = [one_run(n) for n in range(1, int(sys.argv[1]) + 1)]
    for n, r in enumerate(runs, 1):
        print(f"run {n}: up -d called {datetime.fromtimestamp(r['t0']).strftime('%H:%M:%S.%f')[:-3]} (local clock = UTC), "
              f"returned after {r['up_returned'] - r['t0']:.2f} s")
        for (svc, act), t in sorted(r["marks"].items(), key=lambda kv: kv[1]):
            print(f"  docker event  +{t - r['t0']:7.3f} s  {svc:6} {act}")
        print(f"  loader first log line +{r['first_log'] - r['t0']:7.3f} s")
        for step, (a, b, sec) in sorted(r["steps"].items(), key=lambda kv: (kv[1][0], kv[1][1])):
            print(f"  loader step   +{a - r['t0']:7.3f} -> +{b - r['t0']:7.3f} s  {step} ({sec:.3f} s)")
        print(f"  first HTTP 200  /_stcore/health +{r['health'] - r['t0']:.3f} s   / +{r['page'] - r['t0']:.3f} s\n")
    table = [phases(r) for r in runs]
    print(f"{'phase':78} " + " ".join(f"run {n:<3}" for n in range(1, len(runs) + 1)) + "  mean")
    for i, (label, _, _) in enumerate(table[0]):
        vals = [t[i][2] - t[i][1] for t in table]
        print(f"{label:78} " + " ".join(f"{v:7.3f}" for v in vals) + f"  {sum(vals) / len(vals):6.3f}")
    for label, fn in [("TOTAL: up -d called -> first 200 on / (sum of the rows above)", lambda r: r["page"] - r["t0"]),
                      ("up -d called -> first 200 on /_stcore/health (= full_run of the benchmark)", lambda r: r["health"] - r["t0"]),
                      ("pipeline_total (loader: everything after the download)", lambda r: r["steps"]["pipeline_total"][2]),
                      ("full_run - pipeline_total (the 'fixed part' of README / qa_bank A6)",
                       lambda r: r["health"] - r["t0"] - r["steps"]["pipeline_total"][2])]:
        vals = [fn(r) for r in runs]
        print(f"{label:78} " + " ".join(f"{v:7.3f}" for v in vals) + f"  {sum(vals) / len(vals):6.3f}")


if __name__ == "__main__":
    main()
