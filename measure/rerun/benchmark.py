"""Measures the project at 25%, 50% and 100% of the labels, three runs each.

    python3 measure/rerun/benchmark.py

Run it from the repository root with Docker running. It needs only Python, no packages.
Every run starts from an empty database, in a Compose project of its own on port 8601,
so a demo running on 8080 is not touched.

"first" start: the loader reads the 14 zips. "later" start: it reads the saved CSV.
The zips must already be in data/raw, the download is not measured.

Output: measure/rerun/results/runs.csv (every value), summary.md (the means), machine.txt.
"""
import csv
import json
import os
import platform
import subprocess
import threading
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
RESULTS = HERE / "results"
SIZES = ["0.25", "0.5", "1.0"]
RUNS = 3
STARTS = {"later": "1", "first": "0"}  # the value of EXTRACT_CACHE
PORT = "8601"
PROJECT = "drug-explorer-bench"
COMPOSE = ["docker", "compose", "-p", PROJECT]
STEPS = ["parse", "read_extract", "copy", "index_build", "build_drugs", "pipeline_total"]


def sh(command, env=None):
    done = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
    if done.returncode:
        raise SystemExit(done.stderr)
    return done.stdout


def to_mib(text):
    """'235.4MiB / 7.7GiB' -> 235.4"""
    used = text.split("/")[0].strip()
    number = used.rstrip("KMGiB")
    return float(number) * {"B": 1 / 1024 ** 2, "KiB": 1 / 1024, "MiB": 1, "GiB": 1024}[used[len(number):]]


def watch_memory(peak, stop):
    """Asks docker stats about once a second and keeps the highest value of each container."""
    while not stop.is_set():
        stats = sh(["docker", "stats", "--no-stream", "--format", "{{.Name}} {{.MemUsage}}"])
        for line in stats.splitlines():
            name, used = line.split(" ", 1)
            if name.startswith(PROJECT):
                service = name.split("-")[3]  # drug-explorer-bench-loader-1
                peak[service] = max(peak[service], to_mib(used))
        time.sleep(1)


def page_answers():
    try:
        urllib.request.urlopen(f"http://localhost:{PORT}/health", timeout=2)
        return True
    except OSError:
        return False


def one_run(size, start):
    env = os.environ | {"SAMPLE_FRACTION": size, "EXTRACT_CACHE": STARTS[start], "APP_PORT": PORT}
    sh(COMPOSE + ["down", "-v"], env)

    peak, stop = defaultdict(float), threading.Event()
    watcher = threading.Thread(target=watch_memory, args=(peak, stop))
    watcher.start()
    began = time.perf_counter()
    sh(COMPOSE + ["up", "-d"], env)
    while not page_answers():
        time.sleep(0.2)
    values = {"full_run_s": round(time.perf_counter() - began, 2)}
    stop.set()
    watcher.join()
    for service, mib in peak.items():
        values[f"peak_mib_{service}"] = round(mib, 1)

    timings = sh(COMPOSE + ["exec", "-T", "db", "sh", "-c",
                            'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F, '
                            '-c "SELECT step, seconds FROM pipeline_timings"'], env)
    for line in timings.splitlines():
        step, seconds = line.split(",")
        if step in STEPS:
            values[f"{step}_s"] = round(float(seconds), 2)

    queries = sh(COMPOSE + ["run", "--rm", "--no-deps", "-T", "-v", f"{HERE}:/measure:ro",
                            "-e", "PYTHONPATH=/app", "app", "python", "/measure/time_queries.py"], env)
    values |= json.loads(queries)
    print(size, start, values, flush=True)
    return values


def machine():
    lines = [time.strftime("date: %Y-%m-%d %H:%M"), "system: " + platform.platform()]
    if platform.system() == "Darwin":
        lines.append("processor: " + sh(["sysctl", "-n", "machdep.cpu.brand_string"]).strip())
        lines.append("ram_bytes: " + sh(["sysctl", "-n", "hw.memsize"]).strip())
    lines.append("docker: " + sh(["docker", "info", "--format",
                                  "{{.ServerVersion}}, {{.NCPU}} CPUs, {{.MemTotal}} bytes"]).strip())
    zips = Path(os.environ.get("DATA_PATH", ROOT / "data")) / "raw"
    lines.append(f"zip_bytes: {sum(f.stat().st_size for f in zips.glob('*.zip'))}")
    return "\n".join(lines) + "\n"


def summary(rows):
    values = defaultdict(list)
    for row in rows:
        values[row["metric"], row["start"], row["size"]].append(row["value"])
    text = "| Metric | Start | 25% | 50% | 100% |\n|---|---|---|---|---|\n"
    for metric in sorted({row["metric"] for row in rows}):
        for start in STARTS:
            cells = [values.get((metric, start, size)) for size in SIZES]
            if any(cells):
                means = [f"{sum(cell) / len(cell):.2f}" if cell else "" for cell in cells]
                text += f"| {metric} | {start} | " + " | ".join(means) + " |\n"
    return text


def main():
    RESULTS.mkdir(exist_ok=True)
    sh(COMPOSE + ["build"])
    (RESULTS / "machine.txt").write_text(machine())
    one_run(SIZES[0], "later")  # not recorded, it only makes sure the saved CSV is there

    rows = []
    for run in range(1, RUNS + 1):
        # the sizes take turns, so a slow minute of the laptop does not land on one size only
        for size in SIZES:
            for start in STARTS:
                for metric, value in one_run(size, start).items():
                    rows.append({"size": size, "start": start, "run": run, "metric": metric, "value": value})
                with open(RESULTS / "runs.csv", "w", newline="") as file:
                    writer = csv.DictWriter(file, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)

    sh(COMPOSE + ["down", "-v"])
    (RESULTS / "summary.md").write_text(summary(rows))
    print(summary(rows))


if __name__ == "__main__":
    main()
