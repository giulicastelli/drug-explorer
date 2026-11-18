"""Benchmark: our measurement protocol, run automatically.

  "Run each test 3 times, report the average. Write down the laptop:
   processor and RAM. Change one thing at a time."
  "Run with 25%, 50% and 100% of the data. Does time double when data doubles?"

Runs on the laptop (not in a container), with plain python3 and the standard
library only. It drives docker compose from the repository root:

    python3 measure/benchmark.py --drop-caches                  # 3 sizes x 3 runs (protocol v2)
    python3 measure/benchmark.py --drop-caches --first-start 3  # + 3 first starts at 100% (benchmark v2)
    python3 measure/benchmark.py --sizes 0.25 --runs 1          # quick check

For each (size, run): load average, fresh database volume, OS file cache emptied
(--drop-caches), 30 s settle, load average again, docker compose up, wait until the loader
exited 0 and the dashboard answers, read the loader's step timings from pipeline_timings,
run loader/bench_queries.py (the main query with the GIN index, without it, and on the fly),
and sample docker stats in the background the whole time. Sizes are interleaved and rotated
each round (template D-23). Outputs (in --out): raw_runs.csv, summary.csv,
docker_stats_samples.csv, machine.txt, explain/*.txt.

Benchmark v2 (after the extract cache, commit 565a0a9): data/clean (the extract of the
usable rows) is kept between runs, like data/raw, so the 3 x 3 series (mode "generated")
measures the normal start: read_extract, not parse. --first-start N adds N runs at 100%
(mode "first_start") that delete data/clean first, so the loader parses all 14 zips and
writes the extract again (steps parse + write_extract). In both modes TSV_MODE=generated.

Note: a parse reads all 14 zip files at every size (the hash bucket of a label is known
only after reading it), so "parse" does not shrink with the sample (docs/decision_log.md
D-3). The raw input is therefore the same at every size.
"""
import argparse
import csv
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # the repository root
RAW_COLUMNS = ["size", "run", "step", "value", "unit", "environment", "detail"]
DROP_CACHES = False
SETTLE_S = 30            # wait after down -v (and the cache drop) before the load average and the start
CLEAN = ROOT / "data" / "clean"
STAT_NOTE = ("mean and std over every value of this step (runs x repetitions, pooled); "
             "run_mean_mean and run_mean_std (queries only): the mean of each run's repetitions first, "
             "then mean and std over the runs; std = sample std (n-1)")


def log(msg):
    print(f"[bench {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sh(cmd, timeout=30):
    """Run a command, return its stdout ('' if it fails): used for machine facts."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def compose(*args, env=None, timeout=600, capture=False, check=True):
    """docker compose -p <project> ..., from the repo root, with extra env vars."""
    cmd = ["docker", "compose", "-p", PROJECT, *args]
    return subprocess.run(cmd, cwd=ROOT, env={**os.environ, **(env or {})}, timeout=timeout,
                          check=check, text=True, capture_output=capture)


def read_env():
    path = ROOT / ".env"
    if not path.exists():
        sys.exit("No .env file. Run first: cp .env.example .env")
    pairs = (line.split("=", 1) for line in path.read_text().splitlines() if "=" in line and not line.startswith("#"))
    return {k.strip(): v.strip() for k, v in pairs}


def psql(sql, timeout=120):
    """One query in the db container; returns rows as lists of text (-At: no headers, no padding)."""
    out = compose("exec", "-T", "db", "psql", "-U", ENV["POSTGRES_USER"], "-d", ENV["POSTGRES_DB"],
                  "-At", "-F", ",", "-c", sql, timeout=timeout, capture=True).stdout
    # maxsplit=3: only the last column (detail) may contain commas.
    return [line.split(",", 3) for line in out.splitlines() if line]


def size_label(size):
    return f"{round(size * 100)}%"


# ---------------------------------------------------------------- machine
def machine_info():
    """OS, CPU, cores, RAM of the laptop, and what Docker can use (on a Mac, Docker Desktop's VM)."""
    system = platform.system()
    if system == "Darwin":
        os_name = f"macOS {platform.mac_ver()[0]} ({platform.machine()})"
        cpu = sh(["sysctl", "-n", "machdep.cpu.brand_string"])
        cores = sh(["sysctl", "-n", "hw.ncpu"])
        ram = int(sh(["sysctl", "-n", "hw.memsize"]) or 0)
    elif system == "Linux":
        release = dict(l.split("=", 1) for l in Path("/etc/os-release").read_text().splitlines() if "=" in l)
        os_name = f"{release.get('PRETTY_NAME', 'Linux').strip(chr(34))} (kernel {platform.release()}, {platform.machine()})"
        cpu = next((l.split(":", 1)[1].strip() for l in sh(["lscpu"]).splitlines() if l.startswith("Model name")), "")
        cores = str(os.cpu_count())
        mem_kb = next(l.split()[1] for l in Path("/proc/meminfo").read_text().splitlines() if l.startswith("MemTotal"))
        ram = int(mem_kb) * 1024
    else:
        os_name, cpu, cores, ram = f"{system} {platform.release()}", platform.processor(), str(os.cpu_count()), 0
    docker = sh(["docker", "version", "--format", "{{.Server.Version}}"])
    vm_cpus, _, vm_mem = sh(["docker", "info", "--format", "{{.NCPU}} {{.MemTotal}}"]).partition(" ")
    return {
        "os": os_name, "cpu": cpu or "unknown CPU", "cores": cores, "ram_gib": ram / 2**30,
        "docker": docker, "docker_cpus": vm_cpus, "docker_mem_gib": int(vm_mem or 0) / 2**30,
    }


def environment(m, mode):
    """One string per raw row: the machine and the mode."""
    return (f"{m['os']}; {m['cpu']}; {m['cores']} logical cores; {m['ram_gib']:.1f} GiB RAM; "
            f"Docker {m['docker']} ({m['docker_cpus']} CPUs, {m['docker_mem_gib']:.1f} GiB for containers); "
            f"all measured in docker; mode={mode}")


def image_sizes():
    sizes = {}
    for image in (f"{PROJECT}-loader", f"{PROJECT}-app", "postgres:16"):
        out = sh(["docker", "image", "inspect", "--format", "{{.Size}}", image])
        sizes[image] = int(out) if out.isdigit() else None
    return sizes


def raw_input_sizes():
    """The 14 zip files of the manifest in data/raw, and the JSON inside them (read from the
    zip headers, nothing is unzipped). The same at every size: every file is read."""
    raw = ROOT / "data" / "raw"
    manifest = json.loads((raw / "download.json").read_text(encoding="utf-8"))
    names = [Path(p["file"]).name for p in manifest["results"]["drug"]["label"]["partitions"]]
    zip_bytes = json_bytes = 0
    for name in names:
        zip_bytes += (raw / name).stat().st_size
        with zipfile.ZipFile(raw / name) as z:
            json_bytes += sum(m.file_size for m in z.infolist())
    return len(names), zip_bytes, json_bytes


# ---------------------------------------------------------------- memory
def to_mib(text):
    """'123.4MiB' / '1.2GiB' / '900kB' (docker stats MemUsage) -> MiB."""
    number, unit = re.fullmatch(r"([\d.]+)\s*([A-Za-z]+)", text.strip()).groups()
    factor = {"B": 1, "KiB": 2**10, "MiB": 2**20, "GiB": 2**30, "kB": 1e3, "KB": 1e3, "MB": 1e6, "GB": 1e9}[unit]
    return float(number) * factor / 2**20


class MemorySampler(threading.Thread):
    """docker stats --no-stream, a new call every 0.5 s, in the background.
    Keeps every sample (CSV) and the peak per (phase, service).
    One --no-stream call takes about 2 s (the daemon waits for a fresh reading),
    so a new call starts every 0.5 s and a few of them overlap. Calls that finish together
    return the same reading: it is written once (v2 wrote it once per call, review round 2),
    so distinct readings are about 1 s apart, not 0.5 s. The peak is the same either way."""

    def __init__(self, out_csv, context):
        super().__init__(daemon=True)
        self.out_csv, self.context = out_csv, context
        self.phase = "full_run"                      # changed by the main thread: full_run -> queries
        self.peaks = {}
        self.stop_event = threading.Event()
        # Our containers only: <project>-db-1, <project>-loader-1, <project>-loader-run-<id>, ...
        self.name_re = re.compile(rf"{re.escape(PROJECT)}-([a-z0-9_]+?)-(?:run-[0-9a-f]+|\d+)")

    def run(self):
        t0 = time.perf_counter()
        cmd = ["docker", "stats", "--no-stream", "--format", "{{json .}}"]
        running = []                                 # (phase at start, process) of calls not finished yet
        new = not self.out_csv.exists()
        with open(self.out_csv, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["size", "run", "mode", "phase", "t_s", "container", "service", "mem_mib", "cpu_perc"])
            while not self.stop_event.is_set() or running:
                if not self.stop_event.is_set():
                    running.append((self.phase, subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                                                 stderr=subprocess.DEVNULL, text=True)))
                written = set()                      # (container, memory, cpu) already written in this pass
                for phase, proc in [item for item in running if item[1].poll() is not None]:
                    running.remove((phase, proc))
                    t = f"{time.perf_counter() - t0:.2f}"
                    for line in proc.stdout.read().splitlines():
                        s = json.loads(line)
                        match = self.name_re.fullmatch(s["Name"])
                        if not match or "/" not in s["MemUsage"]:
                            continue
                        if (s["Name"], s["MemUsage"], s["CPUPerc"]) in written:
                            continue                 # the same reading from another call of this pass
                        written.add((s["Name"], s["MemUsage"], s["CPUPerc"]))
                        service, mib = match.group(1), to_mib(s["MemUsage"].split("/")[0])
                        w.writerow([*self.context, phase, t, s["Name"], service, f"{mib:.1f}", s["CPUPerc"]])
                        self.peaks[(phase, service)] = max(self.peaks.get((phase, service), 0.0), mib)
                f.flush()
                time.sleep(0.5 if not self.stop_event.is_set() else 0.1)

    def stop(self):
        self.stop_event.set()
        self.join(timeout=30)


# ---------------------------------------------------------------- waiting
def services_state():
    """docker compose ps -a --format json: one JSON object per line (new compose) or one list (old)."""
    out = compose("ps", "-a", "--format", "json", capture=True, timeout=60).stdout.strip()
    items = json.loads(out) if out.startswith("[") else [json.loads(l) for l in out.splitlines() if l.strip()]
    return {i["Service"]: i for i in items}


def app_healthy(port):
    # No proxy for localhost (a corporate proxy would answer instead of the app).
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://localhost:{port}/_stcore/health", timeout=3) as resp:
            return resp.status == 200
    except OSError:
        return False


def fail_with_logs(service, why):
    log(f"FAILED: {why}. Last lines of the {service} log:")
    compose("logs", "--no-color", "--tail", "60", service, check=False, timeout=60)
    raise SystemExit(1)


def wait_ready(port, timeout):
    """Until the loader exited 0 AND the dashboard answers 200 on /_stcore/health."""
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        loader = services_state().get("loader", {})
        if loader.get("State") == "exited" and loader.get("ExitCode") not in (0, None):
            fail_with_logs("loader", f"loader exited with code {loader.get('ExitCode')}")
        if loader.get("State") == "exited" and loader.get("ExitCode") == 0 and app_healthy(port):
            return
        time.sleep(0.5)
    fail_with_logs("app", f"not ready after {timeout} s (loader state: {loader.get('State')})")


# ---------------------------------------------------------------- one run
def timings_rows(run_ids):
    ids = ", ".join(f"'{r}'" for r in run_ids)
    return psql(f"SELECT step, seconds, rows, detail FROM pipeline_timings WHERE run_id IN ({ids}) "
                "ORDER BY started_at, step")


def to_raw(step, seconds, rows, detail):
    """One pipeline_timings row -> raw_runs rows (step, value, unit, detail). See bench_queries.py for the convention."""
    note = "; ".join(x for x in (f"rows={rows}" if rows else "", detail) if x)
    if step.startswith("query_"):
        return [(step, float(seconds) * 1000, "ms", note)]
    if step.startswith("disk_"):
        name = step.removesuffix("_bytes")
        return [(name, int(rows), "bytes", ""), (name, int(rows) / 1e6, "MB", "")]
    if step.startswith("count_"):
        return [(step, int(rows), "count", detail)]
    if step.startswith("check_"):
        return [(step, int(rows), "bool", detail)]
    if step == "bench_order":
        return [(step, 0, "label", detail)]
    out = [(step, float(seconds), "s", note)]
    if step == "copy":
        out.append(("rows_loaded", int(rows), "rows", ""))
    return out


def save_explains(stdout, size):
    """Cut the EXPLAIN blocks printed by bench_queries.py into explain/<size>pct_<query>_<mode>.txt."""
    folder = OUT / "explain"
    folder.mkdir(parents=True, exist_ok=True)
    pattern = r"----- BEGIN EXPLAIN (\w+) (\w+) -----\n(.*?)\n----- END EXPLAIN -----"
    for query, mode, text in re.findall(pattern, stdout, re.S):
        (folder / f"{round(size * 100)}pct_{query}_{mode}.txt").write_text(text + "\n")


def drop_os_cache(add):
    """Cold start for every run: empty the OS file cache (Linux, root only), so run 1 of a size
    is not the only one that reads the 1.86 GB of zip files from disk."""
    try:
        subprocess.run(["sync"], check=True)
        Path("/proc/sys/vm/drop_caches").write_text("3\n")
        add("os_cache_dropped", 1, "bool", "sync; echo 3 > /proc/sys/vm/drop_caches")
    except (OSError, subprocess.CalledProcessError) as exc:
        log(f"note: could not drop the OS cache ({exc}); this run starts with a warm cache")
        add("os_cache_dropped", 0, "bool", str(exc))


def one_run(size, run, mode, machine, port, timeout):
    """One (size, run): fresh volume, up, wait, read timings, benchmark the queries.
    mode = generated (the normal start: the extract in data/clean is read) |
           first_start (data/clean deleted first: the loader parses the zips and writes the extract)."""
    run_id = f"bench-{size}-r{run}" if mode == "generated" else f"bench-{size}-{mode}-r{run}"
    log(f"=== size {size_label(size)}, run {run}, mode {mode} (RUN_ID={run_id}) ===")
    rows = []

    def add(step, value, unit, detail=""):
        rows.append([size_label(size), run, step, value, unit, environment(machine, mode), detail])

    # 1. Load average BEFORE down -v: how busy the machine was at the end of the previous run.
    load1, load5, _ = os.getloadavg()            # Linux and macOS
    add("machine_load_1min_before_down", load1, "load", f"os.getloadavg() before down -v; 5 min: {load5:.2f}")

    # 2. Equal conditions: remove the containers AND the database volume. ./data/raw stays, and so
    #    does ./data/clean, except in a first start, which deletes the extract.
    compose("down", "-v", "--remove-orphans", timeout=300)
    if mode == "first_start":
        gone = sorted(p.name for p in CLEAN.glob("labels_*.csv*"))
        for name in gone:
            (CLEAN / name).unlink()
        add("extract_deleted", len(gone), "count", " ".join(gone))
    if DROP_CACHES:
        drop_os_cache(add)
    # 3. Settle: down -v, sync and the cache drop are work too. The 1-min load average decays with a
    #    time constant of 1 minute, so 30 s lowers what they add but does not remove it.
    time.sleep(SETTLE_S)
    load1, load5, _ = os.getloadavg()
    add("machine_load_1min_after_settle", load1, "load",
        f"os.getloadavg() after down -v and a {SETTLE_S} s settle, just before up; 5 min: {load5:.2f}")

    sampler = MemorySampler(OUT / "docker_stats_samples.csv", [size_label(size), run, mode])
    sampler.start()
    try:
        # 4. The full run: from "docker compose up" to the dashboard answering.
        env = {"SAMPLE_FRACTION": str(size), "RUN_ID": run_id, "APP_PORT": str(port), "TSV_MODE": "generated"}
        t0 = time.perf_counter()
        # up -d returns once the app has started: the app waits for the loader (service_completed_successfully).
        up = compose("up", "-d", env=env, timeout=timeout, check=False)
        if up.returncode != 0:
            fail_with_logs("loader", "docker compose up failed")
        wait_ready(port, timeout=timeout)
        full_run = time.perf_counter() - t0
        add("full_run", full_run, "s", "docker compose up -d until loader exited 0 and /_stcore/health = 200")
        log(f"full run: {full_run:.1f} s")

        # 5. The loader's own steps. Its run id comes from load_info, in case compose did not pass RUN_ID on.
        loader_id = psql("SELECT value FROM load_info WHERE key = 'run_id'")[0][0]
        if loader_id != run_id:
            log(f"note: the loader used RUN_ID={loader_id} (docker-compose.yml does not pass RUN_ID on)")
        loader_steps = timings_rows([loader_id])
        for step, seconds, n, detail in loader_steps:
            for r in to_raw(step, seconds, n, detail):
                add(*r)
        # The run must have taken the path its mode names, or its numbers would land in the wrong series.
        expected = "parse" if mode == "first_start" else "read_extract"
        if expected not in {row[0] for row in loader_steps}:
            raise SystemExit(f"mode {mode}: the loader did not run the step {expected} (see load_path in load_info)")

        # 6. The queries with, without the index and on the fly (normal starts only: a first start
        #    loads the same rows, so the queries would be the same).
        if mode == "generated":
            sampler.phase = "queries"
            order = "with_first" if run % 2 else "without_first"      # alternate the index state measured first
            log(f"running bench_queries.py (BENCH_ORDER={order}; the on-the-fly variant takes seconds per query)")
            bench = compose("run", "--rm", "--no-deps", "-e", f"RUN_ID={run_id}-queries", "-e", f"BENCH_ORDER={order}",
                            "loader", "python", "bench_queries.py", timeout=timeout, capture=True, check=False)
            print(bench.stdout, end="")
            if bench.returncode != 0:
                print(bench.stderr, file=sys.stderr)
                raise SystemExit(f"bench_queries.py failed (exit {bench.returncode})")
            if run == 1:
                save_explains(bench.stdout, size)
            for step, seconds, n, detail in timings_rows([f"{run_id}-queries"]):
                for r in to_raw(step, seconds, n, detail):
                    add(*r)
        else:
            (db_bytes,), = psql("SELECT pg_database_size(current_database())")
            add("disk_database", int(db_bytes), "bytes")
            add("disk_database", int(db_bytes) / 1e6, "MB")

        # 7. The kept text: the bytes of indications in the database (grows with the sample).
        (text_bytes,), = psql("SELECT sum(octet_length(indications)) FROM labels")
        add("kept_indications_text", int(text_bytes), "bytes", "sum(octet_length(indications)), uncompressed")
        add("kept_indications_text", int(text_bytes) / 1e6, "MB", "sum(octet_length(indications)), uncompressed")
    finally:
        sampler.stop()

    # 8. Peak memory per container.
    for (phase, service), mib in sorted(sampler.peaks.items()):
        add(f"peak_mem_{service}_{phase}", mib, "MiB", "docker stats --no-stream, a new sample every 0.5 s")

    # 9. The raw files a parse reads (all 14 zips at every size) and the extract a later start reads
    #    instead, to compare with the database on disk.
    n_files, zip_bytes, json_bytes = RAW_SIZES
    # the newest extract: an older one (other export or clean rules) may still lie next to it
    extract_bytes = max((p.stat().st_mtime, p.stat().st_size) for p in CLEAN.glob("labels_*.csv"))[1]
    for step, b, note in [("raw_zip", zip_bytes, f"{n_files} zip files in data/raw (read by a parse, at every size)"),
                          ("raw_json", json_bytes, f"the JSON inside the {n_files} zips (zip headers)"),
                          ("extract_csv", extract_bytes, "data/clean/labels_<export_date>_<clean_version>.csv (read by a later start)")]:
        add(step, b, "bytes", note)
        add(step, b / 1e6, "MB", note)
    write_raw(rows)


# ---------------------------------------------------------------- files
def write_raw(rows):
    path = OUT / "raw_runs.csv"
    new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(RAW_COLUMNS)
        w.writerows(rows)
    log(f"{len(rows)} rows appended to {path}")


def write_summary():
    """n, mean, min, max, std, median per (size, mode, step, unit). The _repN suffix of the query
    steps is dropped, so 3 runs x 3 repetitions = 9 values per query (on the fly: 3 runs x 1).
    The pooled std of those 9 mixes the spread inside a run (repetitions on a warm cache) with
    the spread between runs (fresh volume, new load): first review round. So for the
    queries, runs = number of runs, run_mean_mean / run_mean_std = mean and std of the 3 per-run means."""
    path = OUT / "raw_runs.csv"
    if not path.exists():
        return
    groups = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            if r["unit"] == "label":                              # bench_order: text, not a number
                continue
            mode = r["environment"].rsplit("mode=", 1)[-1]
            step = re.sub(r"_rep\d+$", "", r["step"])
            groups.setdefault((r["size"], mode, step, r["unit"]), []).append((r["run"], float(r["value"])))
    with open(OUT / "summary.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["size", "mode", "step", "unit", "n", "mean", "min", "max", "std", "median",
                    "runs", "run_mean_mean", "run_mean_std", "stat_note"])
        for (size, mode, step, unit), pairs in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][2], float(kv[0][0].rstrip("%")))):
            v = [value for _, value in pairs]
            std = f"{statistics.stdev(v):.4g}" if len(v) > 1 else ""      # no spread from one value
            num = lambda x: f"{round(x, 4):.15g}"                         # bytes stay whole numbers
            runs = run_mean = run_std = ""
            if step.startswith("query_"):                                 # first the mean of each run's repetitions
                per_run = {}
                for run, value in pairs:
                    per_run.setdefault(run, []).append(value)
                means = [statistics.mean(x) for x in per_run.values()]
                runs, run_mean = len(means), num(statistics.mean(means))
                run_std = f"{statistics.stdev(means):.4g}" if len(means) > 1 else ""
            w.writerow([size, mode, step, unit, len(v), num(statistics.mean(v)), num(min(v)), num(max(v)), std,
                        num(statistics.median(v)), runs, run_mean, run_std, STAT_NOTE])
    log(f"summary written to {OUT / 'summary.csv'}")


def write_machine(machine, images):
    lines = [f"{k}: {v:.1f}" if isinstance(v, float) else f"{k}: {v}" for k, v in machine.items()]
    lines += ["docker compose: " + sh(["docker", "compose", "version", "--short"]), "", "image sizes (docker image inspect):"]
    lines += [f"  {name}: {b / 1e6:.0f} MB" if b else f"  {name}: not found" for name, b in images.items()]
    lines += ["", "exact versions behind the numbers (the tags postgres:16 and python:3.12-slim move):"]
    for name in ("postgres:16", "python:3.12-slim", f"{PROJECT}-loader"):
        lines.append(f"  {name} image id: " + sh(["docker", "image", "inspect", "--format", "{{.Id}}", name]))
    lines.append("  " + sh(["docker", "run", "--rm", "postgres:16", "postgres", "--version"], timeout=120))
    lines.append("  loader: " + sh(["docker", "run", "--rm", f"{PROJECT}-loader", "python", "-c",
                                    "import sys, ijson, psycopg; print('Python', sys.version.split()[0], '| ijson',"
                                    " ijson.__version__, ijson.backend, '| psycopg', psycopg.__version__)"], timeout=120))
    n_files, zip_bytes, json_bytes = RAW_SIZES
    lines += ["", f"raw input (data/raw): {n_files} zip files, {zip_bytes:,} bytes zipped, {json_bytes:,} bytes of JSON inside",
              f"drop OS cache before every run: {DROP_CACHES}",
              "data/clean (the extract) kept between runs: yes, except in first_start runs, which delete it first",
              f"load average: os.getloadavg() before down -v, and again after down -v, the cache drop and a "
              f"{SETTLE_S} s settle, just before up"]
    (OUT / "machine.txt").write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------- main
def main():
    global PROJECT, ENV, OUT, DROP_CACHES, RAW_SIZES
    p = argparse.ArgumentParser(description="Measurement protocol: sizes x runs, time, memory, disk.")
    p.add_argument("--sizes", default="0.25,0.5,1.0", help="SAMPLE_FRACTION values, comma separated; none = only the first starts")
    p.add_argument("--runs", type=int, default=3, help="runs per size")
    p.add_argument("--project", default="drug-explorer", help="docker compose project name (-p)")
    p.add_argument("--app-port", type=int, default=8501, help="dashboard port on the laptop (APP_PORT)")
    p.add_argument("--first-start", type=int, default=0, metavar="N",
                   help="after the sizes x runs, N runs at 100%% that delete data/clean first (parse + write_extract)")
    p.add_argument("--out", default="measure/results", help="output folder (relative to the repo root)")
    p.add_argument("--timeout", type=int, default=3600, help="seconds allowed for one docker compose up / query run")
    p.add_argument("--order", choices=["blocks", "interleaved"], default="interleaved",
                   help="blocks = all runs of 25%%, then 50%%, then 100%%; interleaved = run 1 of every size, then run 2, "
                        "with the size order rotated each round, so drift and cache state do not line up with size")
    p.add_argument("--drop-caches", action="store_true", help="empty the OS file cache before every run (Linux, root)")
    a = p.parse_args()
    DROP_CACHES = a.drop_caches
    PROJECT, ENV, OUT = a.project, read_env(), (ROOT / a.out).resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "raw_runs.csv").exists():
        log(f"note: {OUT / 'raw_runs.csv'} exists; new rows are appended to it")
    sizes = [float(x) for x in a.sizes.split(",") if x.strip() not in ("", "none")]   # "none": first starts only
    if not (ROOT / "data" / "raw" / "download.json").exists():
        sys.exit("data/raw/download.json is missing: run `docker compose up` once, so the loader downloads "
                 "the 14 files; the benchmark times the pipeline, not the download")
    RAW_SIZES = raw_input_sizes()
    manifest = json.loads((ROOT / "data" / "raw" / "download.json").read_text(encoding="utf-8"))
    # the loader names it labels_<export_date>_<clean_version>.csv (clean_version: see load_fda.py)
    extract = CLEAN / f"labels_{manifest['results']['drug']['label']['export_date']}_*.csv"
    if sizes and not list(CLEAN.glob(extract.name)):
        sys.exit(f"{extract.relative_to(ROOT)} is missing: run `docker compose up` once, so the loader writes "
                 "the extract; the sizes x runs series measures the normal start, which reads it")

    machine = machine_info()
    log("machine: " + environment(machine, "-"))
    t_all = time.perf_counter()
    try:
        log("docker compose build (once, before any timing)")
        compose("build", timeout=1800)
        write_machine(machine, image_sizes())
        if not sizes:           # --sizes none: only the first starts
            schedule = []
        elif a.order == "blocks":
            schedule = [(size, run, "generated") for size in sizes for run in range(1, a.runs + 1)]
        else:   # round r: the sizes rotated by r-1, e.g. 25-50-100, 50-100-25, 100-25-50
            schedule = [(size, run, "generated") for run in range(1, a.runs + 1)
                        for size in sizes[(run - 1) % len(sizes):] + sizes[:(run - 1) % len(sizes)]]
        # The first starts come last, so the sizes x runs series sits where v1's did (round 1 first).
        schedule += [(1.0, run, "first_start") for run in range(1, a.first_start + 1)]
        log("schedule: " + ", ".join(f"{size_label(sz)} r{r}" + ("" if m == "generated" else f" {m}")
                                     for sz, r, m in schedule))
        for size, run, mode in schedule:
            t = time.perf_counter()
            one_run(size, run, mode, machine, a.app_port, a.timeout)
            log(f"iteration took {time.perf_counter() - t:.0f} s")
    except KeyboardInterrupt:
        log("interrupted (Ctrl-C): stopping the stack; the rows of finished runs are kept")
        compose("down", check=False, timeout=300)
        write_summary()
        sys.exit(130)
    except subprocess.TimeoutExpired as exc:
        log(f"FAILED: timeout after {exc.timeout} s: {' '.join(exc.cmd)}")
        compose("down", check=False, timeout=300)
        sys.exit(1)
    # Stop the stack but keep the last database volume (no -v).
    compose("down", timeout=300)
    write_summary()
    log(f"done in {time.perf_counter() - t_all:.0f} s; results in {OUT}")


if __name__ == "__main__":
    main()
