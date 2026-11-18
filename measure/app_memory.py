"""App-memory experiment: the dashboard's peak memory WHILE it serves searches.

Benchmark v1 read the app's memory while nobody used it: its query phase runs
bench_queries.py in the loader image, and the app only answered /_stcore/health
(measure/predictions.md P32; review round 1). Here a browser uses the page.

One fresh stack at 100% (docker compose up -d: db, loader from the extract, app), then
docker stats --no-stream every 0.5 s (benchmark.py's MemorySampler) in three phases:
  idle     20 s after the dashboard answers /_stcore/health, no browser connected
  browser  while measure/app_memory.js runs 8 searches + drill-down, twice (Playwright, Chromium)
  after    20 s after the browser closed
Run from the repository root (host Python 3, standard library; node with playwright):
    python3 measure/app_memory.py
Writes into measure/results_experiments/app_memory/: docker_stats_samples.csv, events.csv,
peaks.csv, and prints the summary.
"""
import csv
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark as b  # noqa: E402  (compose, read_env, wait_ready, MemorySampler)

b.PROJECT, PORT = "de-exp", "8571"
OUT = b.ROOT / "measure" / "results_experiments" / "app_memory"
PHASE_SECONDS = 20


def main():
    b.ENV = b.read_env()
    OUT.mkdir(parents=True, exist_ok=True)
    samples = OUT / "docker_stats_samples.csv"
    samples.unlink(missing_ok=True)
    b.log(f"load average before: {open('/proc/loadavg').read().split()[:3]}")
    b.compose("down", "-v", "--remove-orphans", timeout=300)
    env = {"SAMPLE_FRACTION": "1.0", "APP_PORT": PORT, "RUN_ID": "app-memory-100"}
    t0 = time.perf_counter()
    b.compose("up", "-d", env=env, timeout=600)
    b.wait_ready(PORT, 600)
    b.log(f"dashboard ready after {time.perf_counter() - t0:.1f} s")

    sampler = b.MemorySampler(samples, ["100%", 1, "generated"])
    sampler.phase = "idle"
    sampler.start()
    time.sleep(PHASE_SECONDS)
    sampler.phase = "browser"
    t_browser = time.perf_counter()
    browser = subprocess.run(["node", str(OUT.parent.parent / "app_memory.js"), PORT, str(OUT / "events.csv")],
                             capture_output=True, text=True, timeout=900)
    b.log(f"browser part: {time.perf_counter() - t_browser:.1f} s, exit {browser.returncode}: "
          f"{browser.stdout.strip()} {browser.stderr.strip()[-500:]}")
    sampler.phase = "after"
    time.sleep(PHASE_SECONDS)
    sampler.stop()
    b.compose("down", "-v", timeout=300)

    # idle vs peak per container: the median and the highest sample of each phase
    with open(samples, newline="") as f:
        rows = list(csv.DictReader(f))
    with open(OUT / "peaks.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["service", "phase", "samples", "median_mib", "max_mib", "max_cpu_perc"])
        for service in sorted({r["service"] for r in rows}):
            for phase in ("idle", "browser", "after"):
                mem = [float(r["mem_mib"]) for r in rows if r["service"] == service and r["phase"] == phase]
                cpu = [float(r["cpu_perc"].rstrip("%")) for r in rows if r["service"] == service and r["phase"] == phase]
                if mem:
                    w.writerow([service, phase, len(mem), f"{statistics.median(mem):.1f}", f"{max(mem):.1f}", f"{max(cpu):.1f}"])
                    b.log(f"{service:6} {phase:8} n={len(mem):3} median {statistics.median(mem):6.1f} MiB  "
                          f"max {max(mem):6.1f} MiB  max CPU {max(cpu):.1f}%")
    if browser.returncode != 0:
        raise SystemExit("the browser part failed: see the log above")


if __name__ == "__main__":
    main()
